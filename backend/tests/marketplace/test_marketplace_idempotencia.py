"""`Idempotency-Key` em criar e cancelar anúncio (4.4b, ADR 0014 e 0018).

Cena (conftest): ana vende, bruno é amigo dela. A repetição devolve o corpo GRAVADO na primeira
vez (um retrato), sem executar de novo. A chave não "queima" quando a operação falha: o registro
nasce na mesma transação e desfaz junto. Depois que `expire_idempotency` apaga o registro, criar
de novo volta a funcionar: é o limite aceito (a guarda durável do criar não existe).
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from apps.economy.models import IdempotencyRecord
from apps.marketplace.models import MarketListing

from .conftest import LISTINGS_URL, logado, nova_chave

pytestmark = pytest.mark.django_db


def _criar(cliente: Any, instancia: Any, chave: Any, price: int = 1000) -> Any:
    cabecalhos = {} if chave is None else {"HTTP_IDEMPOTENCY_KEY": chave}
    return cliente.post(
        LISTINGS_URL,
        {"instance_id": str(instancia.pk), "price": price},
        format="json",
        **cabecalhos,
    )


def _cancelar(cliente: Any, listing_id: Any, chave: Any) -> Any:
    cabecalhos = {} if chave is None else {"HTTP_IDEMPOTENCY_KEY": chave}
    return cliente.post(f"{LISTINGS_URL}{listing_id}/cancel/", {}, format="json", **cabecalhos)


# --- criar ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("chave", [None, "", "isto-nao-e-uuid", "123"])
def test_criar_sem_chave_valida_da_400_e_nao_cria_nada(cena: SimpleNamespace, chave: Any) -> None:
    resposta = _criar(logado(cena.ana), cena.a1, chave)

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "invalid_idempotency_key"
    assert MarketListing.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


def test_criar_com_chave_nova_da_201_e_um_anuncio_ativo(cena: SimpleNamespace) -> None:
    resposta = _criar(logado(cena.ana), cena.a1, nova_chave(), price=700)

    assert resposta.status_code == 201, resposta.content
    anuncio = MarketListing.objects.get()
    assert (str(anuncio.pk), anuncio.price, anuncio.status) == (
        resposta.json()["id"],
        700,
        "active",
    )


def test_repetir_o_criar_devolve_o_mesmo_anuncio_sem_criar_outro(cena: SimpleNamespace) -> None:
    ana, chave = logado(cena.ana), nova_chave()
    primeira = _criar(ana, cena.a1, chave)

    repetida = _criar(ana, cena.a1, chave)

    assert (primeira.status_code, repetida.status_code) == (201, 201)
    assert repetida.json() == primeira.json()
    assert MarketListing.objects.count() == 1


def test_repetir_o_criar_depois_de_cancelar_nao_recria_o_anuncio(cena: SimpleNamespace) -> None:
    """O cenário do PENDING: reenviar um criar antigo depois de cancelar recriava o anúncio."""
    ana, chave = logado(cena.ana), nova_chave()
    primeira = _criar(ana, cena.a1, chave)
    assert _cancelar(ana, primeira.json()["id"], nova_chave()).status_code == 200

    repetida = _criar(ana, cena.a1, chave)

    assert repetida.status_code == 201
    assert repetida.json() == primeira.json()  # o retrato da 1ª vez ("active"), não o estado atual
    assert MarketListing.objects.count() == 1
    assert MarketListing.objects.get().status == "cancelled"


@pytest.mark.parametrize("mudanca", ["preco", "item"])
def test_mesma_chave_com_outro_pedido_da_422_e_nao_cria_nada(
    cena: SimpleNamespace, mudanca: str
) -> None:
    ana, chave = logado(cena.ana), nova_chave()
    assert _criar(ana, cena.a1, chave, price=1000).status_code == 201

    if mudanca == "preco":
        outra = _criar(ana, cena.a1, chave, price=999)
    else:
        outra = _criar(ana, cena.a2, chave, price=1000)

    assert outra.status_code == 422
    assert outra.json()["code"] == "idempotency_key_reused"
    assert MarketListing.objects.count() == 1
    assert MarketListing.objects.get().price == 1000


def test_criar_item_ja_anunciado_da_409_e_a_chave_nao_fica_queimada(
    cena: SimpleNamespace,
) -> None:
    ana, chave = logado(cena.ana), nova_chave()
    primeiro = _criar(ana, cena.a1, nova_chave())
    recusado = _criar(ana, cena.a1, chave)
    assert recusado.status_code == 409
    assert recusado.json()["code"] == "item_already_listed"
    assert IdempotencyRecord.objects.filter(key=chave).count() == 0
    assert _cancelar(ana, primeiro.json()["id"], nova_chave()).status_code == 200

    de_novo = _criar(ana, cena.a1, chave)

    assert de_novo.status_code == 201, de_novo.content
    assert MarketListing.objects.filter(status="active").count() == 1


def test_a_chave_do_criar_expirada_deixa_criar_de_novo_limite_aceito(
    cena: SimpleNamespace,
) -> None:
    """Depois que `expire_idempotency` apaga o registro, o criar antigo reenviado recria o
    anúncio. Não há guarda durável (decisão do dono, 2026-11-26); este teste documenta o limite.
    """
    ana, chave = logado(cena.ana), nova_chave()
    primeira = _criar(ana, cena.a1, chave)
    assert _cancelar(ana, primeira.json()["id"], nova_chave()).status_code == 200
    IdempotencyRecord.objects.all().delete()

    repetida = _criar(ana, cena.a1, chave)

    assert repetida.status_code == 201
    assert repetida.json()["id"] != primeira.json()["id"]
    assert MarketListing.objects.count() == 2


# --- cancelar ------------------------------------------------------------------------------------


@pytest.mark.parametrize("chave", [None, "", "isto-nao-e-uuid"])
def test_cancelar_sem_chave_valida_da_400_e_nao_cancela(cena: SimpleNamespace, chave: Any) -> None:
    ana = logado(cena.ana)
    anuncio = _criar(ana, cena.a1, nova_chave()).json()

    resposta = _cancelar(ana, anuncio["id"], chave)

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "invalid_idempotency_key"
    assert MarketListing.objects.get().status == "active"


def test_cancelar_com_chave_nova_da_200_e_fecha_o_anuncio(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    anuncio = _criar(ana, cena.a1, nova_chave()).json()

    resposta = _cancelar(ana, anuncio["id"], nova_chave())

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "cancelled"
    assert MarketListing.objects.get().status == "cancelled"


def test_repetir_o_cancelar_devolve_200_com_o_mesmo_corpo_e_nao_regrava_o_fechamento(
    cena: SimpleNamespace,
) -> None:
    ana, chave = logado(cena.ana), nova_chave()
    anuncio = _criar(ana, cena.a1, nova_chave()).json()
    primeira = _cancelar(ana, anuncio["id"], chave)
    fechado = MarketListing.objects.get().closed_at

    repetida = _cancelar(ana, anuncio["id"], chave)

    assert (primeira.status_code, repetida.status_code) == (200, 200)  # antes era 409
    assert repetida.json() == primeira.json()
    assert MarketListing.objects.get().closed_at == fechado


def test_cancelar_com_a_chave_de_um_criar_da_422_e_nao_cancela(cena: SimpleNamespace) -> None:
    ana, chave = logado(cena.ana), nova_chave()
    anuncio = _criar(ana, cena.a1, chave).json()

    resposta = _cancelar(ana, anuncio["id"], chave)

    assert resposta.status_code == 422
    assert resposta.json()["code"] == "idempotency_key_reused"
    assert MarketListing.objects.get().status == "active"


def test_cancelar_anuncio_de_outra_pessoa_da_404_e_a_chave_nao_fica_queimada(
    cena: SimpleNamespace,
) -> None:
    anuncio = _criar(logado(cena.ana), cena.a1, nova_chave()).json()
    chave = nova_chave()

    resposta = _cancelar(logado(cena.bruno), anuncio["id"], chave)

    assert resposta.status_code == 404
    assert IdempotencyRecord.objects.filter(key=chave).count() == 0
    assert MarketListing.objects.get().status == "active"


def test_a_chave_vale_por_jogador_a_mesma_chave_de_outro_jogador_nao_colide(
    cena: SimpleNamespace,
) -> None:
    chave = str(uuid.uuid4())
    da_ana = _criar(logado(cena.ana), cena.a1, chave)

    do_bruno = _criar(logado(cena.bruno), cena.b1, chave)

    assert (da_ana.status_code, do_bruno.status_code) == (201, 201)
    assert da_ana.json()["id"] != do_bruno.json()["id"]
