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


def test_primeiro_resgate_paga_2_50_dolares_e_lanca_no_ledger(ana: Any) -> None:
    claim = services.claim_daily(ana, now=T0)

    assert claim.streak_day == 1
    assert claim.claim_number == 1
    assert claim.amount == 250
    assert _saldo(ana) == 2_750
    linhas = WalletTransaction.objects.filter(group_id=claim.ledger_group_id)
    assert {(t.wallet.kind, t.amount, t.kind) for t in linhas} == {
        ("player", 250, "daily_reward"),
        ("system", -250, "daily_reward"),
    }


def test_dias_seguidos_pagam_2_50_5_7_50_dolares(ana: Any) -> None:
    pagos = [services.claim_daily(ana, now=T0 + i * 24 * H).amount for i in range(3)]

    assert pagos == [250, 500, 750]
    assert _saldo(ana) == 2_500 + 1_500


def test_pular_um_dia_volta_ao_dia_1(ana: Any) -> None:
    services.claim_daily(ana, now=T0)
    services.claim_daily(ana, now=T0 + 24 * H)

    depois = services.claim_daily(ana, now=T0 + 24 * H + 48 * H)

    assert depois.streak_day == 1
    assert depois.amount == 250
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
    assert _saldo(ana) == 2_750
    assert DailyClaim.objects.filter(user=ana).count() == 1


def test_resgate_libera_exatamente_em_24h(ana: Any) -> None:
    services.claim_daily(ana, now=T0)

    segundo = services.claim_daily(ana, now=T0 + 24 * H)

    assert segundo.streak_day == 2


def test_sequencia_para_de_crescer_no_dia_14(ana: Any) -> None:
    pagos = [services.claim_daily(ana, now=T0 + i * 24 * H) for i in range(45)]

    assert pagos[12].amount == 3_250  # dia 13
    assert pagos[13].amount == 3_500  # dia 14
    assert pagos[14].amount == 3_500  # dia 15
    assert pagos[44].amount == 3_500  # dia 45
    assert pagos[44].streak_day == 45  # a contagem segue; só o valor tem teto


def test_cada_jogador_tem_a_propria_sequencia(ana: Any, bruno: Any) -> None:
    services.claim_daily(ana, now=T0)
    services.claim_daily(ana, now=T0 + 24 * H)

    primeiro_do_bruno = services.claim_daily(bruno, now=T0 + 24 * H)

    assert primeiro_do_bruno.streak_day == 1
    assert _saldo(bruno) == 2_750


def test_status_informa_se_pode_resgatar_e_quanto_paga(ana: Any) -> None:
    antes = services.get_wallet_status(ana, now=T0)
    services.claim_daily(ana, now=T0)
    depois = services.get_wallet_status(ana, now=T0 + 10 * H)
    liberado = services.get_wallet_status(ana, now=T0 + 24 * H)

    assert (antes.can_claim, antes.next_streak_day, antes.next_amount) == (True, 1, 250)
    assert depois.can_claim is False
    assert depois.available_at == T0 + 24 * H
    assert (liberado.can_claim, liberado.next_streak_day, liberado.next_amount) == (
        True,
        2,
        500,
    )


def test_banco_recusa_dois_resgates_com_o_mesmo_numero(ana: Any) -> None:
    claim = services.claim_daily(ana, now=T0)

    with pytest.raises(IntegrityError), transaction.atomic():
        DailyClaim.objects.create(
            user=ana,
            claim_number=claim.claim_number,
            claimed_at=T0 + 30 * H,
            streak_day=1,
            amount=250,
            ledger_group_id=uuid.uuid4(),
        )
