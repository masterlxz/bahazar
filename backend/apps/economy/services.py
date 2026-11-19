"""Casca transacional da economia: única porta de escrita de saldo e ledger (GUIDELINES 2).

Ordem de travas: carteiras SEMPRE em ordem de UUID (evita deadlock quando houver 2+ jogadores).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import rules
from .models import DailyClaim, TransactionKind, Wallet, WalletKind, WalletTransaction


class Entry(NamedTuple):
    """Uma linha de lançamento: quanto entra (+) ou sai (-) de uma carteira."""

    wallet_id: uuid.UUID
    amount: int


class EconomyError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "economy_error"
    message = "Operação não permitida."


class InsufficientFunds(EconomyError):
    code = "insufficient_funds"
    message = "Saldo insuficiente."


class DailyNotReady(EconomyError):
    code = "daily_not_ready"
    message = "A diária ainda não está disponível."

    def __init__(self, available_at: datetime) -> None:
        super().__init__(self.message)
        self.available_at = available_at


@dataclass(frozen=True)
class WalletStatus:
    balance: int
    can_claim: bool
    available_at: datetime | None
    next_streak_day: int
    next_amount: int


def _now() -> datetime:
    """Relógio do serviço. Existe para os testes o substituírem (`monkeypatch`)."""
    return timezone.now()


def get_system_wallet() -> Wallet:
    """A carteira `system` global. Cria na primeira vez, tolerando corrida entre processos."""
    existente = Wallet.objects.filter(kind=WalletKind.SYSTEM).first()
    if existente is not None:
        return existente
    try:
        with transaction.atomic():
            return Wallet.objects.create(kind=WalletKind.SYSTEM)
    except IntegrityError:  # outra requisição criou primeiro (UNIQUE parcial da `system`)
        return Wallet.objects.get(kind=WalletKind.SYSTEM)


def post_entries(
    entries: list[Entry],
    *,
    kind: str,
    ref_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> uuid.UUID:
    """Grava um lançamento de partida dobrada e devolve o `group_id`.

    Tudo ou nada: valida a soma zero, trava as carteiras em ordem de UUID, recusa saldo de
    jogador negativo e atualiza `balance` na mesma transação das linhas do ledger.
    """
    ids = [e.wallet_id for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("a mesma carteira aparece duas vezes no lançamento")

    grupo = uuid.uuid4()
    with transaction.atomic():
        carteiras = {
            w.id: w for w in Wallet.objects.select_for_update().filter(id__in=ids).order_by("id")
        }
        if len(carteiras) != len(ids):
            raise ValueError("carteira inexistente no lançamento")

        linhas: list[WalletTransaction] = []
        for entrada in entries:
            carteira = carteiras[entrada.wallet_id]
            novo_saldo = carteira.balance + entrada.amount
            if carteira.kind == WalletKind.PLAYER and novo_saldo < 0:
                raise InsufficientFunds
            carteira.balance = novo_saldo
            linhas.append(
                WalletTransaction(
                    wallet=carteira,
                    group_id=grupo,
                    amount=entrada.amount,
                    balance_after=novo_saldo,
                    kind=kind,
                    ref_id=ref_id,
                    idempotency_key=idempotency_key or "",
                )
            )
        Wallet.objects.bulk_update(carteiras.values(), ["balance"])
        WalletTransaction.objects.bulk_create(linhas)
    return grupo


def open_wallet(user: Any) -> Wallet:
    """Abre a carteira do jogador e lança o saldo inicial, uma única vez."""
    with transaction.atomic():
        carteira, _ = Wallet.objects.get_or_create(user=user, defaults={"kind": WalletKind.PLAYER})
        carteira = Wallet.objects.select_for_update().get(pk=carteira.pk)
        ja_recebeu = WalletTransaction.objects.filter(
            wallet=carteira, kind=TransactionKind.STARTING_GRANT
        ).exists()
        if not ja_recebeu:
            sistema = get_system_wallet()
            post_entries(
                [
                    Entry(sistema.id, -rules.STARTING_BALANCE),
                    Entry(carteira.id, rules.STARTING_BALANCE),
                ],
                kind=TransactionKind.STARTING_GRANT,
                idempotency_key=f"starting_grant:{user.pk}",
            )
        return Wallet.objects.get(pk=carteira.pk)


def ensure_wallet(user: Any) -> Wallet:
    """Auto-cura: se a carteira não existe (falha no cadastro), abre agora."""
    carteira = Wallet.objects.filter(user=user).first()
    return carteira if carteira is not None else open_wallet(user)


def claim_daily(user: Any, now: datetime | None = None) -> DailyClaim:
    """Resgata a diária. Liberada 24h depois do último resgate; sequência de 24h a 48h.

    A trava da linha da carteira serializa resgates do mesmo jogador; o UNIQUE
    `(user, claim_number)` é a rede de segurança do banco.
    """
    agora = now if now is not None else _now()
    with transaction.atomic():
        carteira = Wallet.objects.select_for_update().get(pk=ensure_wallet(user).pk)
        ultimo = DailyClaim.objects.filter(user=user).order_by("-claim_number").first()
        decorrido = None if ultimo is None else agora - ultimo.claimed_at

        if ultimo is not None and not rules.can_claim(decorrido):
            raise DailyNotReady(available_at=ultimo.claimed_at + rules.DAILY_WINDOW)

        sequencia = rules.next_streak_day(ultimo.streak_day if ultimo else None, decorrido)
        numero = (ultimo.claim_number if ultimo else 0) + 1
        valor = rules.daily_amount(sequencia)
        sistema = get_system_wallet()
        grupo = post_entries(
            [Entry(sistema.id, -valor), Entry(carteira.id, valor)],
            kind=TransactionKind.DAILY_REWARD,
            idempotency_key=f"daily:{user.pk}:{numero}",
        )
        return DailyClaim.objects.create(
            user=user,
            claim_number=numero,
            claimed_at=agora,
            streak_day=sequencia,
            amount=valor,
            ledger_group_id=grupo,
        )


def get_wallet_status(user: Any, now: datetime | None = None) -> WalletStatus:
    """Saldo e situação da diária (leitura; não trava nada)."""
    agora = now if now is not None else _now()
    carteira = ensure_wallet(user)
    ultimo = DailyClaim.objects.filter(user=user).order_by("-claim_number").first()
    decorrido = None if ultimo is None else agora - ultimo.claimed_at
    liberado = ultimo is None or rules.can_claim(decorrido)
    # Se ainda não liberou, o próximo resgate acontecerá em 24h (dentro da janela da sequência).
    para_sequencia = decorrido if liberado else rules.DAILY_WINDOW
    proximo_dia = rules.next_streak_day(ultimo.streak_day if ultimo else None, para_sequencia)
    return WalletStatus(
        balance=carteira.balance,
        can_claim=liberado,
        available_at=None if liberado or ultimo is None else ultimo.claimed_at + rules.DAILY_WINDOW,
        next_streak_day=proximo_dia,
        next_amount=rules.daily_amount(proximo_dia),
    )
