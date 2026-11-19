"""Diária em sequência com janela de 24h por resgate (sem fuso: nada a manipular)."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from apps.economy import services
from apps.economy.models import DailyClaim, Wallet, WalletTransaction

from .conftest import T0

pytestmark = pytest.mark.django_db

H = timedelta(hours=1)


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def test_primeiro_resgate_paga_10_dolares_e_lanca_no_ledger(ana: Any) -> None:
    claim = services.claim_daily(ana, now=T0)

    assert claim.streak_day == 1
    assert claim.claim_number == 1
    assert claim.amount == 1_000
    assert _saldo(ana) == 11_000
    linhas = WalletTransaction.objects.filter(group_id=claim.ledger_group_id)
    assert {(t.wallet.kind, t.amount, t.kind) for t in linhas} == {
        ("player", 1_000, "daily_reward"),
        ("system", -1_000, "daily_reward"),
    }


def test_dias_seguidos_pagam_10_20_30_dolares(ana: Any) -> None:
    pagos = [services.claim_daily(ana, now=T0 + i * 24 * H).amount for i in range(3)]

    assert pagos == [1_000, 2_000, 3_000]
    assert _saldo(ana) == 10_000 + 6_000


def test_pular_um_dia_volta_ao_dia_1(ana: Any) -> None:
    services.claim_daily(ana, now=T0)
    services.claim_daily(ana, now=T0 + 24 * H)

    depois = services.claim_daily(ana, now=T0 + 24 * H + 48 * H)

    assert depois.streak_day == 1
    assert depois.amount == 1_000
    assert depois.claim_number == 3


def test_limite_da_sequencia_nas_bordas_de_24h_e_48h(ana: Any, bruno: Any) -> None:
    services.claim_daily(ana, now=T0)
    ainda_na_sequencia = services.claim_daily(ana, now=T0 + 48 * H - timedelta(seconds=1))
    services.claim_daily(bruno, now=T0)
    perdeu = services.claim_daily(bruno, now=T0 + 48 * H)

    assert ainda_na_sequencia.streak_day == 2
    assert perdeu.streak_day == 1


def test_resgatar_antes_de_24h_e_recusado_e_nao_credita(ana: Any) -> None:
    services.claim_daily(ana, now=T0)

    with pytest.raises(services.DailyNotReady) as erro:
        services.claim_daily(ana, now=T0 + 24 * H - timedelta(seconds=1))

    assert erro.value.available_at == T0 + 24 * H
    assert _saldo(ana) == 11_000
    assert DailyClaim.objects.filter(user=ana).count() == 1


def test_resgate_libera_exatamente_em_24h(ana: Any) -> None:
    services.claim_daily(ana, now=T0)

    segundo = services.claim_daily(ana, now=T0 + 24 * H)

    assert segundo.streak_day == 2


def test_sequencia_para_de_crescer_no_dia_30(ana: Any) -> None:
    pagos = [services.claim_daily(ana, now=T0 + i * 24 * H) for i in range(45)]

    assert pagos[28].amount == 29_000
    assert pagos[29].amount == 30_000  # dia 30
    assert pagos[30].amount == 30_000  # dia 31
    assert pagos[44].amount == 30_000  # dia 45
    assert pagos[44].streak_day == 45  # a contagem segue; só o valor tem teto


def test_cada_jogador_tem_a_propria_sequencia(ana: Any, bruno: Any) -> None:
    services.claim_daily(ana, now=T0)
    services.claim_daily(ana, now=T0 + 24 * H)

    primeiro_do_bruno = services.claim_daily(bruno, now=T0 + 24 * H)

    assert primeiro_do_bruno.streak_day == 1
    assert _saldo(bruno) == 11_000


def test_status_informa_se_pode_resgatar_e_quanto_paga(ana: Any) -> None:
    antes = services.get_wallet_status(ana, now=T0)
    services.claim_daily(ana, now=T0)
    depois = services.get_wallet_status(ana, now=T0 + 10 * H)
    liberado = services.get_wallet_status(ana, now=T0 + 24 * H)

    assert (antes.can_claim, antes.next_streak_day, antes.next_amount) == (True, 1, 1_000)
    assert depois.can_claim is False
    assert depois.available_at == T0 + 24 * H
    assert (liberado.can_claim, liberado.next_streak_day, liberado.next_amount) == (
        True,
        2,
        2_000,
    )


def test_banco_recusa_dois_resgates_com_o_mesmo_numero(ana: Any) -> None:
    claim = services.claim_daily(ana, now=T0)

    with pytest.raises(IntegrityError), transaction.atomic():
        DailyClaim.objects.create(
            user=ana,
            claim_number=claim.claim_number,
            claimed_at=T0 + 30 * H,
            streak_day=1,
            amount=1_000,
            ledger_group_id=uuid.uuid4(),
        )
