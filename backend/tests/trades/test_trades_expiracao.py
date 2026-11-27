"""Expiração das ofertas pendentes (`expire_trade_offers`): decisão do dono, 2026-11-27.

Uma oferta `pending` com `created_at` ESTRITAMENTE anterior a `agora - N dias` vira `expired` e
solta os itens. O prazo de 7 dias é HIPÓTESE sem fonte. O relógio do comando é fixado em T0
(`expiry._now`); a idade da oferta é gravada direto (`created_at` é `auto_now_add`).
"""

import uuid
from datetime import UTC, datetime, timedelta
from io import StringIO
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest import MonkeyPatch
from rest_framework.test import APIClient

from apps.trades import expiry, rules, services
from apps.trades.expiry import MAX_DAYS
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_instancia

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)
DIA = timedelta(days=1)
PRAZO = 7


@pytest.fixture(autouse=True)
def relogio_parado(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(expiry, "_now", lambda: T0)


def _oferta(cena: SimpleNamespace, skin: Any, idade: timedelta, resolver: str | None = None) -> Any:
    """Oferta de ana para bruno com itens novos, criada `idade` antes de T0.

    `resolver` (`accept`, `decline`, `cancel`) a leva a um estado terminal antes de envelhecer.
    """
    dela = criar_instancia(cena.ana, skin)
    dele = criar_instancia(cena.bruno, skin)
    oferta = services.create_offer(cena.ana, cena.bruno, [dela.id], [dele.id])
    if resolver == "accept":
        services.accept_offer(cena.bruno, oferta.id)
    elif resolver == "decline":
        services.decline_offer(cena.bruno, oferta.id)
    elif resolver == "cancel":
        services.cancel_offer(cena.ana, oferta.id)
    TradeOffer.objects.filter(pk=oferta.pk).update(created_at=T0 - idade)
    return TradeOffer.objects.get(pk=oferta.pk)


def _retrato(oferta: TradeOffer) -> tuple[str, datetime | None, int]:
    atual = TradeOffer.objects.get(pk=oferta.pk)
    ativos = TradeOfferItem.objects.filter(offer=atual, active=True).count()
    return atual.status, atual.resolved_at, ativos


def _comando(*args: str) -> str:
    saida = StringIO()
    call_command("expire_trade_offers", *args, stdout=saida)
    return saida.getvalue()


# --- quem expira ---------------------------------------------------------------------------------


def test_pendente_mais_velha_que_o_prazo_expira_e_solta_os_itens(
    cena: SimpleNamespace, skin: Any
) -> None:
    oferta = _oferta(cena, skin, 8 * DIA)

    assert expiry.expire_offers(days=PRAZO) == 1

    status, fim, ativos = _retrato(oferta)
    assert (status, fim is not None, ativos) == ("expired", True, 0)


@pytest.mark.parametrize("dias", [PRAZO, PRAZO - 1], ids=["exatamente no corte", "6 dias"])
def test_pendente_que_ainda_nao_passou_do_corte_continua_pendente(
    cena: SimpleNamespace, skin: Any, dias: int
) -> None:
    oferta = _oferta(cena, skin, dias * DIA)

    assert expiry.expire_offers(days=PRAZO) == 0

    assert _retrato(oferta) == ("pending", None, 2)


@pytest.mark.parametrize("acao", ["accept", "decline", "cancel"])
def test_oferta_ja_resolvida_nunca_e_tocada(cena: SimpleNamespace, skin: Any, acao: str) -> None:
    oferta = _oferta(cena, skin, 30 * DIA, resolver=acao)
    antes = _retrato(oferta)

    assert expiry.expire_offers(days=PRAZO) == 0

    assert _retrato(oferta) == antes
    assert antes[0] != "pending"


def test_so_as_vencidas_expiram_numa_mesma_rodada(cena: SimpleNamespace, skin: Any) -> None:
    velha = _oferta(cena, skin, 9 * DIA)
    nova = _oferta(cena, skin, 1 * DIA)

    assert expiry.expire_offers(days=PRAZO) == 1

    assert (_retrato(velha)[0], _retrato(nova)[0]) == ("expired", "pending")


def test_rodar_de_novo_nao_acha_mais_nada(cena: SimpleNamespace, skin: Any) -> None:
    _oferta(cena, skin, 8 * DIA)

    assert (expiry.expire_offers(days=PRAZO), expiry.expire_offers(days=PRAZO)) == (1, 0)


def test_dry_run_conta_e_nao_grava(cena: SimpleNamespace, skin: Any) -> None:
    oferta = _oferta(cena, skin, 8 * DIA)

    assert expiry.expire_offers(days=PRAZO, dry_run=True) == 1

    assert _retrato(oferta) == ("pending", None, 2)


def test_depois_de_expirar_os_mesmos_itens_entram_em_oferta_nova(
    cena: SimpleNamespace, skin: Any
) -> None:
    oferta = _oferta(cena, skin, 8 * DIA)
    itens = {i.side: i.instance_id for i in oferta.items.all()}
    expiry.expire_offers(days=PRAZO)

    nova = services.create_offer(cena.ana, cena.bruno, [itens["offered"]], [itens["requested"]])

    assert nova.status == "pending"


# --- prazo inválido ------------------------------------------------------------------------------


@pytest.mark.parametrize("dias", [0, -1, MAX_DAYS + 1])
def test_prazo_fora_da_faixa_e_recusado_e_nada_muda(
    cena: SimpleNamespace, skin: Any, dias: int
) -> None:
    oferta = _oferta(cena, skin, 30 * DIA)

    with pytest.raises(ValueError, match="days"):
        expiry.expire_offers(days=dias)
    with pytest.raises(CommandError, match="--days"):
        _comando("--days", str(dias))

    assert _retrato(oferta) == ("pending", None, 2)


# --- o comando -----------------------------------------------------------------------------------


def test_o_comando_usa_o_prazo_padrao_de_7_dias_e_informa_o_total(
    cena: SimpleNamespace, skin: Any
) -> None:
    velha = _oferta(cena, skin, 8 * DIA)
    nova = _oferta(cena, skin, 6 * DIA)

    saida = _comando()

    assert "Expiradas 1 oferta(s) pendente(s) com mais de 7 dia(s)." in saida
    assert (_retrato(velha)[0], _retrato(nova)[0]) == ("expired", "pending")


def test_o_comando_em_dry_run_diz_que_nada_foi_alterado(cena: SimpleNamespace, skin: Any) -> None:
    oferta = _oferta(cena, skin, 8 * DIA)

    saida = _comando("--dry-run", "--days", "3")

    assert "Dry-run: 1 oferta(s) pendente(s) com mais de 3 dia(s) seriam expiradas." in saida
    assert "Nada foi alterado." in saida
    assert _retrato(oferta)[0] == "pending"


# --- o serviço de uma oferta e as regras ---------------------------------------------------------


def test_expirar_uma_oferta_ja_aceita_devolve_falso_e_nao_altera(
    cena: SimpleNamespace, skin: Any
) -> None:
    oferta = _oferta(cena, skin, 30 * DIA, resolver="accept")
    antes = _retrato(oferta)

    assert services.expire_offer(oferta.pk) is False

    assert _retrato(oferta) == antes


def test_expirar_uma_oferta_que_nao_existe_devolve_falso() -> None:
    assert services.expire_offer(uuid.uuid4()) is False


def test_ninguem_expira_pela_api_e_a_acao_produz_expired(cena: SimpleNamespace) -> None:
    for ator in (cena.ana.id, cena.bruno.id):
        assert not rules.may_act(
            rules.EXPIRE, actor_id=ator, proposer_id=cena.ana.id, recipient_id=cena.bruno.id
        )
    assert rules.status_after(rules.EXPIRE) == "expired"


def test_as_duas_pontas_leem_a_oferta_expirada_com_o_estado_novo(
    cena: SimpleNamespace, skin: Any
) -> None:
    oferta = _oferta(cena, skin, 8 * DIA)
    expiry.expire_offers(days=PRAZO)

    for jogador in (cena.ana, cena.bruno):
        cliente = APIClient()
        cliente.force_authenticate(jogador)
        resposta = cliente.get("/api/v1/trades/")
        assert resposta.status_code == 200
        assert [(o["id"], o["status"]) for o in resposta.json()["results"]] == [
            (str(oferta.pk), "expired")
        ]
