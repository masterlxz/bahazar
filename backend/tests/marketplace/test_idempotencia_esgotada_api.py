"""Esgotamento do `run_once` nas rotas: 503 `idempotency_unavailable`, nada muda, repetir é seguro.

O `run_once` REAL esgota as tentativas quando o registro `(escopo, chave)` existe (o `INSERT`
falha por unicidade) e some a cada `SELECT` (aqui: `IdempotencyRecord.objects.get` levanta
`DoesNotExist`, o efeito de a expiração apagá-lo no meio). O pedido NÃO executou: o cliente pode
repetir com a MESMA chave, e a API tem de dizer isso (503), não "erro do servidor" (500).
"""

import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.economy.audit import check_ledger
from apps.economy.models import IdempotencyRecord, Wallet
from apps.inventory.models import SkinInstance
from apps.marketplace.models import MarketListing
from apps.trades import services as trades_services
from apps.trades.models import TradeOffer

from .conftest import anunciar, logado

pytestmark = pytest.mark.django_db

SALDO_INICIAL = 2_500
CODIGO = "idempotency_unavailable"


def _esgotar(monkeypatch: pytest.MonkeyPatch, usuario: Any, chave: str) -> None:
    """O registro da chave existe e `get` não o encontra: o `run_once` esgota as tentativas."""
    IdempotencyRecord.objects.create(scope=f"user:{usuario.pk}", key=chave, request_hash="x")

    def get(*args: Any, **kwargs: Any) -> IdempotencyRecord:
        raise IdempotencyRecord.DoesNotExist

    monkeypatch.setattr(IdempotencyRecord.objects, "get", get)


def _passar(monkeypatch: pytest.MonkeyPatch) -> None:
    """O problema passa: o `get` volta ao normal e o registro velho (expirado) some."""
    monkeypatch.undo()
    IdempotencyRecord.objects.all().delete()


def _trocas_criar(cena: SimpleNamespace) -> SimpleNamespace:
    corpo = {
        "recipient": cena.bruno.username,
        "offered": [str(cena.a1.pk)],
        "requested": [str(cena.b1.pk)],
    }
    return SimpleNamespace(
        usuario=cena.ana,
        url="/api/v1/trades/",
        corpo=corpo,
        sucesso=201,
        intacto=lambda: TradeOffer.objects.count() == 0,
    )


def _trocas_cancelar(cena: SimpleNamespace) -> SimpleNamespace:
    oferta = trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])
    return SimpleNamespace(
        usuario=cena.ana,
        url=f"/api/v1/trades/{oferta.pk}/cancel/",
        corpo={},
        sucesso=200,
        intacto=lambda: TradeOffer.objects.get(pk=oferta.pk).status == "pending",
    )


def _mercado_criar(cena: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        usuario=cena.ana,
        url="/api/v1/listings/",
        corpo={"instance_id": str(cena.a1.pk), "price": 1000},
        sucesso=201,
        intacto=lambda: MarketListing.objects.count() == 0,
    )


def _mercado_cancelar(cena: SimpleNamespace) -> SimpleNamespace:
    anuncio = anunciar(cena.ana, cena.a1)
    return SimpleNamespace(
        usuario=cena.ana,
        url=f"/api/v1/listings/{anuncio.pk}/cancel/",
        corpo={},
        sucesso=200,
        intacto=lambda: MarketListing.objects.get(pk=anuncio.pk).status == "active",
    )


def _mercado_comprar(cena: SimpleNamespace) -> SimpleNamespace:
    anuncio = anunciar(cena.ana, cena.a1)

    def intacto() -> bool:
        return (
            SkinInstance.objects.get(pk=cena.a1.pk).owner_id == cena.ana.pk
            and MarketListing.objects.get(pk=anuncio.pk).status == "active"
            and Wallet.objects.get(user=cena.bruno).balance == SALDO_INICIAL
            and Wallet.objects.get(user=cena.ana).balance == SALDO_INICIAL
            and check_ledger() == []
        )

    return SimpleNamespace(
        usuario=cena.bruno,
        url=f"/api/v1/listings/{anuncio.pk}/buy/",
        corpo={},
        sucesso=201,
        intacto=intacto,
    )


ROTAS: dict[str, Callable[[SimpleNamespace], SimpleNamespace]] = {
    "criar troca": _trocas_criar,
    "cancelar troca": _trocas_cancelar,
    "criar anúncio": _mercado_criar,
    "cancelar anúncio": _mercado_cancelar,
    "comprar anúncio": _mercado_comprar,
}


def _enviar(cliente: APIClient, rota: SimpleNamespace, chave: str) -> Any:
    return cliente.post(rota.url, rota.corpo, format="json", HTTP_IDEMPOTENCY_KEY=chave)


@pytest.mark.parametrize("nome", ROTAS)
def test_chave_esgotada_da_503_e_nada_muda(
    cena: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, nome: str
) -> None:
    rota = ROTAS[nome](cena)
    chave = str(uuid.uuid4())
    _esgotar(monkeypatch, rota.usuario, chave)

    resposta = _enviar(logado(rota.usuario), rota, chave)

    assert resposta.status_code == 503, resposta.content
    assert set(resposta.json()) == {"code", "message"}
    assert resposta.json()["code"] == CODIGO
    assert rota.intacto()
    assert IdempotencyRecord.objects.count() == 1  # só o registro velho que montei


@pytest.mark.parametrize("nome", ROTAS)
def test_depois_que_o_problema_passa_a_mesma_chave_executa_normalmente(
    cena: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, nome: str
) -> None:
    """Repetir com a MESMA chave é seguro: a 503 não executou nada nem queimou a chave."""
    rota = ROTAS[nome](cena)
    chave = str(uuid.uuid4())
    _esgotar(monkeypatch, rota.usuario, chave)
    cliente = logado(rota.usuario)
    assert _enviar(cliente, rota, chave).status_code == 503
    _passar(monkeypatch)

    repetida = _enviar(cliente, rota, chave)

    assert repetida.status_code == rota.sucesso, repetida.content
    assert not rota.intacto()
