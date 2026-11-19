"""Ledger: lançamentos atômicos, soma zero, saldo de jogador nunca negativo e imutabilidade."""

import uuid
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, IntegrityError, transaction

from apps.economy import audit, services
from apps.economy.models import Wallet, WalletTransaction

pytestmark = pytest.mark.django_db


def _carteiras(usuario: Any) -> tuple[Wallet, Wallet]:
    return Wallet.objects.get(user=usuario), Wallet.objects.get(kind="system")


def _estado() -> dict[str, int]:
    return {
        "linhas": WalletTransaction.objects.count(),
        **{str(w.id): w.balance for w in Wallet.objects.all()},
    }


# --- lançamentos ------------------------------------------------------------------------------


def test_lancamento_que_nao_soma_zero_e_recusado_e_nao_grava_nada(ana: Any) -> None:
    carteira, sistema = _carteiras(ana)
    antes = _estado()

    with pytest.raises(ValueError):
        services.post_entries(
            [services.Entry(sistema.id, -100), services.Entry(carteira.id, 50)], kind="adjustment"
        )

    assert _estado() == antes


def test_lancamento_que_deixaria_o_jogador_negativo_e_recusado_por_inteiro(ana: Any) -> None:
    carteira, sistema = _carteiras(ana)
    antes = _estado()

    with pytest.raises(services.InsufficientFunds):
        services.post_entries(
            [services.Entry(carteira.id, -10_001), services.Entry(sistema.id, 10_001)],
            kind="adjustment",
        )

    assert _estado() == antes


def test_jogador_pode_chegar_a_zero_mas_nao_abaixo(ana: Any) -> None:
    carteira, sistema = _carteiras(ana)

    services.post_entries(
        [services.Entry(carteira.id, -10_000), services.Entry(sistema.id, 10_000)],
        kind="adjustment",
    )

    carteira.refresh_from_db()
    assert carteira.balance == 0
    with pytest.raises(services.InsufficientFunds):
        services.post_entries(
            [services.Entry(carteira.id, -1), services.Entry(sistema.id, 1)], kind="adjustment"
        )


def test_lancamento_guarda_o_saldo_depois_de_cada_linha(ana: Any) -> None:
    carteira, sistema = _carteiras(ana)

    services.post_entries(
        [services.Entry(carteira.id, -2_500), services.Entry(sistema.id, 2_500)],
        kind="adjustment",
    )

    ultima = WalletTransaction.objects.filter(wallet=carteira).order_by("-created_at", "-id")[0]
    assert ultima.amount == -2_500
    assert ultima.balance_after == 7_500


@pytest.mark.parametrize("valor", [0, 2**63, -(2**63) - 1])
def test_valor_nulo_ou_fora_do_bigint_e_recusado(ana: Any, valor: int) -> None:
    carteira, sistema = _carteiras(ana)

    with pytest.raises(ValueError):
        services.post_entries(
            [services.Entry(carteira.id, valor), services.Entry(sistema.id, -valor)],
            kind="adjustment",
        )


# --- imutabilidade (trigger) ------------------------------------------------------------------


def test_banco_recusa_editar_uma_linha_do_extrato(ana: Any) -> None:
    carteira, _ = _carteiras(ana)

    with pytest.raises(DatabaseError), transaction.atomic():
        WalletTransaction.objects.filter(wallet=carteira).update(amount=1)


def test_banco_recusa_apagar_uma_linha_do_extrato(ana: Any) -> None:
    carteira, _ = _carteiras(ana)

    with pytest.raises(DatabaseError), transaction.atomic():
        WalletTransaction.objects.filter(wallet=carteira).delete()


# --- constraints das carteiras ----------------------------------------------------------------


def test_banco_recusa_segunda_carteira_system(ana: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Wallet.objects.create(kind="system", user=None)


def test_banco_recusa_segunda_carteira_do_mesmo_jogador(ana: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Wallet.objects.create(kind="player", user=ana)


def test_banco_recusa_carteira_de_jogador_sem_dono(ana: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Wallet.objects.create(kind="player", user=None)


def test_banco_recusa_carteira_system_com_dono(bruno: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Wallet.objects.filter(kind="system").update(user=bruno)


def test_banco_recusa_saldo_negativo_de_jogador(ana: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Wallet.objects.filter(user=ana).update(balance=-1)


def test_banco_aceita_saldo_negativo_da_carteira_system(ana: Any) -> None:
    Wallet.objects.filter(kind="system").update(balance=-999_999)

    assert Wallet.objects.get(kind="system").balance == -999_999


def test_banco_recusa_linha_de_extrato_com_valor_zero(ana: Any) -> None:
    carteira, _ = _carteiras(ana)

    with pytest.raises(IntegrityError), transaction.atomic():
        WalletTransaction.objects.create(
            wallet=carteira, group_id=uuid.uuid4(), amount=0, balance_after=0, kind="adjustment"
        )


# --- auditoria --------------------------------------------------------------------------------


def test_auditoria_nao_acha_problema_num_ledger_integro(ana: Any, bruno: Any) -> None:
    assert audit.check_ledger() == []
    call_command("audit_ledger")  # não levanta


def test_auditoria_detecta_saldo_adulterado(ana: Any) -> None:
    Wallet.objects.filter(user=ana).update(balance=10_005)

    problemas = audit.check_ledger()

    assert problemas
    with pytest.raises(CommandError):
        call_command("audit_ledger")


def test_auditoria_detecta_lancamento_que_nao_soma_zero(ana: Any) -> None:
    carteira, _ = _carteiras(ana)
    WalletTransaction.objects.create(
        wallet=carteira, group_id=uuid.uuid4(), amount=7, balance_after=10_007, kind="adjustment"
    )

    assert audit.check_ledger()
    with pytest.raises(CommandError):
        call_command("audit_ledger")
