"""Toda conta nasce com carteira e saldo inicial lançado no ledger (soma zero)."""

from typing import Any

import pytest
from django.db.models import Sum

from apps.economy import audit, services
from apps.economy.models import Wallet, WalletTransaction

from .conftest import User, criar_usuario

pytestmark = pytest.mark.django_db


def test_cadastro_cria_carteira_com_o_saldo_inicial(ana: Any) -> None:
    carteira = Wallet.objects.get(user=ana)

    assert carteira.kind == "player"
    assert carteira.balance == 10_000


def test_saldo_inicial_e_um_lancamento_de_duas_linhas_que_soma_zero(ana: Any) -> None:
    carteira = Wallet.objects.get(user=ana)
    sistema = Wallet.objects.get(kind="system")

    linha_ana = WalletTransaction.objects.get(wallet=carteira)
    linhas_do_grupo = WalletTransaction.objects.filter(group_id=linha_ana.group_id)

    assert linha_ana.kind == "starting_grant"
    assert linha_ana.amount == 10_000
    assert linha_ana.balance_after == 10_000
    assert {(t.wallet_id, t.amount) for t in linhas_do_grupo} == {
        (carteira.id, 10_000),
        (sistema.id, -10_000),
    }
    assert sistema.balance == -10_000


def test_tres_cadastros_mantem_as_invariantes_do_ledger() -> None:
    for nome in ("ana_01", "bruno_02", "carla_03"):
        criar_usuario(nome)

    assert Wallet.objects.get(kind="system").balance == -30_000
    assert WalletTransaction.objects.aggregate(total=Sum("amount"))["total"] == 0
    for carteira in Wallet.objects.all():
        soma = WalletTransaction.objects.filter(wallet=carteira).aggregate(t=Sum("amount"))["t"]
        assert carteira.balance == soma
    assert audit.check_ledger() == []


def test_usuario_criado_direto_pelo_orm_tambem_ganha_carteira() -> None:
    admin = User.objects.create_superuser(
        username="admin_x", email="admin_x@exemplo.com", password="Tr0ub4dor&3-horse-battery"
    )

    assert Wallet.objects.get(user=admin).balance == 10_000


def test_saldo_inicial_nao_e_concedido_duas_vezes(ana: Any) -> None:
    services.open_wallet(ana)
    services.open_wallet(ana)

    assert Wallet.objects.filter(user=ana).count() == 1
    assert Wallet.objects.get(user=ana).balance == 10_000
    assert WalletTransaction.objects.filter(wallet__user=ana, kind="starting_grant").count() == 1
