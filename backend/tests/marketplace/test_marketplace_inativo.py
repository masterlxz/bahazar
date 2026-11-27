"""Compra com um jogador desativado (`is_active=False`): 409 `player_unavailable` (J4).

Decisões do dono (2026-11-27): resposta genérica (um `code` só) e a regra vale só ao AGIR, isto é,
ao comprar; o anúncio de quem foi desativado segue na vitrine (esconder ficou como pendência).
O jogador é desativado direto no banco (`.update`), de propósito: os objetos `User` em memória
seguem com `is_active=True`, então só uma leitura do banco, sob a trava dos jogadores, passa.
Saldo inicial 2.500 (`economy.rules.STARTING_BALANCE`); taxa de 5% (hipótese do dono).
"""

from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.economy.audit import check_ledger
from apps.economy.models import Wallet
from apps.inventory.models import SkinInstance
from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketTransaction

from .conftest import LISTINGS_URL, anunciar, logado, nova_chave

pytestmark = pytest.mark.django_db

CODE = "player_unavailable"
SALDO_INICIAL = 2_500
User: Any = get_user_model()


def _desativar(usuario: Any) -> None:
    User.objects.filter(pk=usuario.pk).update(is_active=False)


def _reativar(usuario: Any) -> None:
    User.objects.filter(pk=usuario.pk).update(is_active=True)


def _comprar(cliente: APIClient, listing_id: Any, chave: str | None = None) -> Any:
    return cliente.post(
        f"{LISTINGS_URL}{listing_id}/buy/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=chave or nova_chave(),
    )


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def _nada_mudou(cena: SimpleNamespace, anuncio: Any) -> None:
    assert SkinInstance.objects.get(pk=anuncio.instance_id).owner_id == cena.ana.pk
    anuncio.refresh_from_db()
    assert (anuncio.status, anuncio.closed_at) == (ListingStatus.ACTIVE, None)
    assert MarketTransaction.objects.count() == 0
    assert (_saldo(cena.bruno), _saldo(cena.ana)) == (SALDO_INICIAL, SALDO_INICIAL)
    assert check_ledger() == []


def test_comprar_de_vendedor_desativado_da_409_e_nada_se_move(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    _desativar(cena.ana)

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    assert resposta.status_code == 409
    assert set(resposta.json()) == {"code", "message"}
    assert resposta.json()["code"] == CODE
    _nada_mudou(cena, anuncio)


def test_comprador_desativado_tambem_e_recusado_no_servico(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    _desativar(cena.bruno)

    with pytest.raises(services.PlayerUnavailable):
        services.buy_listing(cena.bruno, anuncio.pk, idempotency_key=nova_chave())

    _nada_mudou(cena, anuncio)


def test_a_recusa_nao_queima_a_chave_e_reativado_a_mesma_chave_compra(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    chave = nova_chave()
    _desativar(cena.ana)
    assert _comprar(logado(cena.bruno), anuncio.pk, chave).status_code == 409
    _reativar(cena.ana)

    resposta = _comprar(logado(cena.bruno), anuncio.pk, chave)

    assert resposta.status_code == 201, resposta.content
    assert SkinInstance.objects.get(pk=anuncio.instance_id).owner_id == cena.bruno.pk
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000


def test_repetir_uma_compra_ja_feita_devolve_o_recibo_mesmo_com_o_vendedor_desativado_depois(
    cena: SimpleNamespace,
) -> None:
    """A compra já aconteceu: o replay devolve o recibo gravado, sem rodar a regra de novo."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    chave = nova_chave()
    primeira = _comprar(logado(cena.bruno), anuncio.pk, chave)
    assert primeira.status_code == 201
    _desativar(cena.ana)

    segunda = _comprar(logado(cena.bruno), anuncio.pk, chave)

    assert segunda.status_code == 201
    assert segunda.json() == primeira.json()
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000  # debitou uma vez só
