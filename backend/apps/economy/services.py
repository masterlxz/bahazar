"""Casca transacional da economia: única porta de escrita de saldo e ledger (GUIDELINES 2).

Ordem de travas (ADR 0016): jogadores antes de carteiras, e as carteiras SEMPRE em ordem de UUID
(evita deadlock quando houver 2+ jogadores). Quem trava uma carteira à mão antes de chamar
`post_entries` pode formar ciclo com quem trava a `system` e depois a carteira dele.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import idempotency, rules
from .models import DailyClaim, TransactionKind, Wallet, WalletKind, WalletTransaction


class Entry(NamedTuple):
    """Uma linha de lançamento: quanto entra (+) ou sai (-) de uma carteira.

    `kind` é opcional: sem ele a linha leva o tipo do lançamento. Com ele, o extrato distingue
    os papéis de uma mesma operação (compra, venda e taxa de uma compra no mercado).
    """

    wallet_id: uuid.UUID
    amount: int
    kind: str | None = None


class EconomyError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "economy_error"
    message = "Operação não permitida."


class InsufficientFunds(EconomyError):
    code = "insufficient_funds"
    message = "Saldo insuficiente."


class InvalidTransfer(EconomyError):
    code = "invalid_transfer"
    message = "Transferência inválida."


class PlayerUnavailable(EconomyError):
    code = "player_unavailable"
    message = "Este jogador não está disponível."


@dataclass(frozen=True)
class TransferResult:
    ledger_group_id: uuid.UUID
    amount: int
    replayed: bool


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
    rules.validate_entries([e.amount for e in entries])
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
                    kind=entrada.kind or kind,
                    ref_id=ref_id,
                    idempotency_key=idempotency_key or "",
                )
            )
        Wallet.objects.bulk_update(carteiras.values(), ["balance"])
        WalletTransaction.objects.bulk_create(linhas)
    return grupo


def open_wallet(user: Any) -> Wallet:
    """Abre a carteira do jogador e lança o saldo inicial, uma única vez.

    A trava é a do USUÁRIO, e não a da carteira: a ordem global é jogadores antes de carteiras
    (ADR 0016), e as carteiras são travadas depois, por `post_entries`, junto com a `system` e por
    `id`. Travar a carteira à mão ANTES formava o mesmo ciclo da diária com quem segura a `system`
    e depois pede a carteira (a compra). A trava do usuário serializa aberturas simultâneas do
    mesmo jogador; o UNIQUE `(carteira, chave)` do ledger é a rede de segurança do banco.
    """
    with transaction.atomic():
        usuario_model: Any = get_user_model()
        list(usuario_model.objects.select_for_update().filter(pk=user.pk))
        carteira, _ = Wallet.objects.get_or_create(user=user, defaults={"kind": WalletKind.PLAYER})
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


def transfer(sender: Any, recipient: Any, amount: int, *, idempotency_key: str) -> TransferResult:
    """Transfere `amount` centavos de `sender` para `recipient`, uma única vez por chave.

    Repetir a mesma chave com o mesmo pedido devolve o resultado original (`replayed=True`) sem
    mover dinheiro; a mesma chave com outro pedido levanta `IdempotencyKeyReused`. Não há rota
    HTTP (decisão de 2026-11-25): é a base das trocas e do mercado.

    - `ValueError`: a chave não é um UUID.
    - `InvalidTransfer`: valor inválido, ou remetente igual ao destinatário.
    - `InsufficientFunds`: o remetente não tem o valor; nada é gravado.
    - `PlayerUnavailable`: o remetente ou o destinatário está desativado (`is_active=False`,
      risco J4). A leitura é do banco, SEM trava de jogador: travar aqui inverteria a ordem
      jogador→carteira do ADR 0016. A janela de corrida com uma desativação é de milissegundos.
    """
    chave = rules.normalize_idempotency_key(idempotency_key)
    try:
        rules.validate_transfer_amount(amount)
    except ValueError as erro:
        raise InvalidTransfer from erro
    if sender.pk == recipient.pk:
        raise InvalidTransfer
    pedido = rules.request_fingerprint("transfer", str(sender.pk), str(recipient.pk), amount)
    # As carteiras abrem ANTES da transação da idempotência: dentro dela, o `open_wallet` travaria
    # a `system` fora da ordem de UUID que `post_entries` segue (risco de deadlock A↔B).
    origem = ensure_wallet(sender)
    destino = ensure_wallet(recipient)

    def operar() -> tuple[int, dict[str, Any]]:
        grupo = post_entries(
            [Entry(origem.id, -amount), Entry(destino.id, amount)],
            kind=TransactionKind.TRANSFER,
            # Com o remetente no nome: o UNIQUE é por carteira, e a chave vem do cliente.
            idempotency_key=f"transfer:{sender.pk}:{chave}",
        )
        return 201, {"ledger_group_id": str(grupo), "amount": amount}

    saida = idempotency.run_once(
        scope=f"user:{sender.pk}", key=chave, request_hash=pedido, operation=operar
    )
    return TransferResult(
        uuid.UUID(saida.body["ledger_group_id"]), saida.body["amount"], saida.replayed
    )


def claim_daily(user: Any, now: datetime | None = None) -> DailyClaim:
    """Resgata a diária. Liberada 24h depois do último resgate; sequência de 24h a 48h.

    A trava da linha do USUÁRIO serializa resgates do mesmo jogador; o UNIQUE
    `(user, claim_number)` é a rede de segurança do banco. Trava-se o usuário, e não a carteira,
    porque a ordem global é jogadores antes de carteiras (ADR 0016): a carteira é travada depois,
    por `post_entries`, junto com a `system` e por `id`. Travar a carteira ANTES formava um ciclo
    com a compra (que trava a `system` e depois a carteira do jogador, quando `system.id` é o
    menor): deadlock, e 500 para um dos dois. A carteira abre antes da transação, como em
    `transfer`: `open_wallet` trava a `system`, e isso dentro da transação seria fora de ordem.
    """
    agora = now if now is not None else _now()
    carteira = ensure_wallet(user)
    with transaction.atomic():
        usuario_model: Any = get_user_model()
        list(usuario_model.objects.select_for_update().filter(pk=user.pk))
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
