"""Comprar um anúncio pela API: item, dinheiro, taxa e ledger na mesma transação (ADR 0018).

Posse e dinheiro são área de risco (AGENTS §4). Os valores esperados vêm de fora do código sob
teste: saldo inicial 2.500 (`economy.rules.STARTING_BALANCE`) e taxa de 5% arredondada para
baixo (decisão do dono, 2026-11-26, HIPÓTESE ainda não medida).
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.economy import services as economy
from apps.economy.audit import check_ledger
from apps.economy.models import Wallet, WalletTransaction
from apps.friends import services as friends
from apps.inventory.models import SkinInstance
from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketListing, MarketTransaction

from .conftest import LISTINGS_URL, anunciar, logado

pytestmark = pytest.mark.django_db

SALDO_INICIAL = 2_500
UM_ID_QUALQUER = "7c0f8e1a-0000-4000-8000-000000000001"


def _chave() -> str:
    return str(uuid.uuid4())


def _url(listing_id: Any) -> str:
    return f"{LISTINGS_URL}{listing_id}/buy/"


def _comprar(cliente: APIClient, listing_id: Any, chave: str | None = None) -> Any:
    return cliente.post(_url(listing_id), {}, format="json", HTTP_IDEMPOTENCY_KEY=chave or _chave())


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def _saldo_system() -> int:
    return Wallet.objects.get(kind="system").balance


def _nada_mudou(cena: SimpleNamespace, anuncio: MarketListing, preco: int) -> None:
    assert SkinInstance.objects.get(pk=anuncio.instance_id).owner_id == cena.ana.pk
    anuncio.refresh_from_db()
    assert anuncio.status == ListingStatus.ACTIVE
    assert anuncio.closed_at is None
    assert MarketTransaction.objects.count() == 0
    assert _saldo(cena.bruno) == SALDO_INICIAL
    assert _saldo(cena.ana) == SALDO_INICIAL
    assert preco > 0
    assert check_ledger() == []


# --- o caminho feliz ---------------------------------------------------------------------------


def test_comprar_move_o_item_o_dinheiro_e_a_taxa_e_grava_a_venda(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    antes_system = _saldo_system()

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    assert resposta.status_code == 201, resposta.content
    corpo = resposta.json()
    assert set(corpo) == {"id", "listing_id", "price", "fee", "ledger_group_id"}
    assert (corpo["listing_id"], corpo["price"], corpo["fee"]) == (str(anuncio.pk), 1000, 50)

    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000
    assert _saldo(cena.ana) == SALDO_INICIAL + 950
    assert _saldo_system() == antes_system + 50

    cena.a1.refresh_from_db()
    assert cena.a1.owner_id == cena.bruno.pk
    assert str(cena.a1.float_value) == "0.123456789"  # a compra só troca o dono
    anuncio.refresh_from_db()
    assert anuncio.status == ListingStatus.SOLD
    assert anuncio.closed_at is not None

    venda = MarketTransaction.objects.get()
    assert (venda.listing_id, venda.buyer_id, venda.seller_id) == (
        anuncio.pk,
        cena.bruno.pk,
        cena.ana.pk,
    )
    assert (venda.price, venda.fee, str(venda.ledger_group_id)) == (
        1000,
        50,
        corpo["ledger_group_id"],
    )
    assert str(venda.pk) == corpo["id"]


def test_o_ledger_da_compra_tem_uma_linha_por_papel_e_soma_zero(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    linhas = WalletTransaction.objects.filter(group_id=resposta.json()["ledger_group_id"])
    sistema = Wallet.objects.get(kind="system")
    por_carteira = {(linha.wallet_id, linha.amount, linha.kind) for linha in linhas}
    assert por_carteira == {
        (Wallet.objects.get(user=cena.bruno).id, -1000, "market_purchase"),
        (Wallet.objects.get(user=cena.ana).id, 950, "market_sale"),
        (sistema.id, 50, "market_fee"),
    }
    assert {linha.ref_id for linha in linhas} == {anuncio.pk}
    assert check_ledger() == []


@pytest.mark.parametrize(("preco", "taxa"), [(19, 0), (20, 1), (21, 1)])
def test_preco_pequeno_paga_taxa_zero_e_o_ledger_fica_com_duas_linhas(
    cena: SimpleNamespace, preco: int, taxa: int
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, preco)

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    assert resposta.status_code == 201, resposta.content
    assert resposta.json()["fee"] == taxa
    linhas = WalletTransaction.objects.filter(group_id=resposta.json()["ledger_group_id"])
    assert linhas.count() == (3 if taxa else 2)
    assert _saldo(cena.ana) == SALDO_INICIAL + preco - taxa
    assert check_ledger() == []


# --- recusas, sem mudar nada -------------------------------------------------------------------


def test_saldo_insuficiente_da_422_nao_muda_nada_e_a_chave_nao_queima(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 3000)
    bruno = logado(cena.bruno)
    chave = _chave()

    recusada = _comprar(bruno, anuncio.pk, chave)

    assert recusada.status_code == 422
    assert recusada.json()["code"] == "insufficient_funds"
    _nada_mudou(cena, anuncio, 3000)

    economy.post_entries(
        [
            economy.Entry(Wallet.objects.get(kind="system").id, -1000),
            economy.Entry(Wallet.objects.get(user=cena.bruno).id, 1000),
        ],
        kind="adjustment",
    )
    aceita = _comprar(bruno, anuncio.pk, chave)

    assert aceita.status_code == 201, aceita.content
    cena.a1.refresh_from_db()
    assert cena.a1.owner_id == cena.bruno.pk


def test_comprar_o_proprio_anuncio_da_409_e_nao_muda_nada(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    resposta = _comprar(logado(cena.ana), anuncio.pk)

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "cannot_buy_own_listing"
    _nada_mudou(cena, anuncio, 1000)


def test_anuncio_cancelado_ou_ja_vendido_da_409(cena: SimpleNamespace) -> None:
    cancelado = anunciar(cena.ana, cena.a1, 1000)
    assert logado(cena.ana).post(f"{LISTINGS_URL}{cancelado.pk}/cancel/", {}).status_code == 200
    vendido = anunciar(cena.ana, cena.a2, 1000)
    assert _comprar(logado(cena.bruno), vendido.pk).status_code == 201

    um = _comprar(logado(cena.carla), cancelado.pk)
    outro = _comprar(logado(cena.carla), vendido.pk)

    assert (um.status_code, um.json()["code"]) == (409, "listing_not_active")
    assert (outro.status_code, outro.json()["code"]) == (409, "listing_not_active")
    assert MarketTransaction.objects.count() == 1


def test_anuncio_inexistente_e_anuncio_escondido_pelo_bloqueio_dao_o_mesmo_404(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    bruno = logado(cena.bruno)
    inexistente = _comprar(bruno, UM_ID_QUALQUER)

    friends.block(cena.bruno, cena.ana.username)
    escondido = _comprar(bruno, anuncio.pk)

    assert inexistente.status_code == 404
    assert escondido.status_code == 404
    assert escondido.json() == inexistente.json()
    _nada_mudou(cena, anuncio, 1000)


def test_o_bloqueado_compra_do_bloqueador_como_qualquer_um(cena: SimpleNamespace) -> None:
    """ADR 0017: o bloqueio muda só a vista de quem bloqueou; a compra do bloqueado segue igual."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    friends.block(cena.ana, cena.bruno.username)

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    assert resposta.status_code == 201, resposta.content


@pytest.mark.parametrize("mudanca", ["consumo", "dono"])
def test_item_que_saiu_do_jogo_ou_mudou_de_dono_sob_o_anuncio_da_409_e_nao_move_nada(
    cena: SimpleNamespace, mudanca: str
) -> None:
    """Um `UPDATE` direto (admin, trade-up) não passa pela guarda: a compra reconfere sob trava."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    if mudanca == "consumo":
        SkinInstance.objects.filter(pk=cena.a1.pk).update(consumed_at=datetime.now(UTC))
    else:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(owner=cena.carla)

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "listing_unavailable"
    anuncio.refresh_from_db()
    assert anuncio.status == ListingStatus.ACTIVE
    assert MarketTransaction.objects.count() == 0
    assert _saldo(cena.bruno) == SALDO_INICIAL
    assert _saldo(cena.ana) == SALDO_INICIAL
    assert check_ledger() == []


# --- idempotência e cabeçalho ------------------------------------------------------------------


def test_repetir_a_mesma_chave_devolve_a_mesma_resposta_e_debita_uma_vez(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    bruno = logado(cena.bruno)
    chave = _chave()

    primeira = _comprar(bruno, anuncio.pk, chave)
    segunda = _comprar(bruno, anuncio.pk, chave)

    assert primeira.status_code == segunda.status_code == 201
    assert primeira.json() == segunda.json()
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000
    assert _saldo(cena.ana) == SALDO_INICIAL + 950
    assert MarketTransaction.objects.count() == 1
    assert check_ledger() == []


def test_a_mesma_chave_para_outro_anuncio_da_422(cena: SimpleNamespace) -> None:
    um, outro = anunciar(cena.ana, cena.a1, 1000), anunciar(cena.ana, cena.a2, 1000)
    bruno = logado(cena.bruno)
    chave = _chave()
    assert _comprar(bruno, um.pk, chave).status_code == 201

    resposta = _comprar(bruno, outro.pk, chave)

    assert resposta.status_code == 422
    assert resposta.json()["code"] == "idempotency_key_reused"
    assert MarketTransaction.objects.count() == 1


@pytest.mark.parametrize("cabecalho", [None, "", "nao-e-uuid", "123"])
def test_sem_chave_valida_da_400_e_nao_compra(cena: SimpleNamespace, cabecalho: str | None) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    extra = {} if cabecalho is None else {"HTTP_IDEMPOTENCY_KEY": cabecalho}

    resposta = logado(cena.bruno).post(_url(anuncio.pk), {}, format="json", **extra)

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "invalid_idempotency_key"
    _nada_mudou(cena, anuncio, 1000)


def test_o_corpo_da_compra_nao_decide_nada(cena: SimpleNamespace) -> None:
    """Preço, dono e taxa nunca vêm do cliente: um corpo cheio de campos é ignorado."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    resposta = logado(cena.bruno).post(
        _url(anuncio.pk),
        {"price": 1, "fee": 0, "seller": str(cena.bruno.pk), "buyer": str(cena.carla.pk)},
        format="json",
        HTTP_IDEMPOTENCY_KEY=_chave(),
    )

    assert resposta.status_code == 201, resposta.content
    assert resposta.json()["price"] == 1000
    assert MarketTransaction.objects.get().buyer_id == cena.bruno.pk


def test_anonimo_nao_compra(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    resposta = APIClient().post(_url(anuncio.pk), {}, format="json", HTTP_IDEMPOTENCY_KEY=_chave())

    assert resposta.status_code in (401, 403)
    _nada_mudou(cena, anuncio, 1000)


@pytest.mark.parametrize("metodo", ["get", "put", "patch", "delete"])
def test_a_rota_de_compra_so_aceita_post(cena: SimpleNamespace, metodo: str) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    resposta = getattr(logado(cena.bruno), metodo)(_url(anuncio.pk))

    assert resposta.status_code == 405


def test_o_servico_devolve_a_venda_e_marca_a_repeticao(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    chave = _chave()

    primeira = services.buy_listing(cena.bruno, anuncio.pk, idempotency_key=chave)
    repetida = services.buy_listing(cena.bruno, anuncio.pk, idempotency_key=chave)

    assert (primeira.replayed, repetida.replayed) == (False, True)
    assert (primeira.id, primeira.price, primeira.fee) == (repetida.id, 1000, 50)
