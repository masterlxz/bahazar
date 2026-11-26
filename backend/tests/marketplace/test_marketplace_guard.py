"""Guarda de `marketplace` sobre a posse de itens e a guarda de `trades` vista do mercado.

Os dois sentidos da regra: um item com anúncio ativo não muda de dono (`change_owner` recusa sem
o crachá), e um item preso numa oferta pendente não pode ser anunciado (`item_locked`). Sem a
primeira, a compra (4.4) moveria um item anunciado sem fechar o anúncio; sem a segunda, o anúncio
ficaria preso a um item que outra operação pode levar.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance
from apps.marketplace import guards, services
from apps.marketplace.models import ListingStatus, MarketListing
from apps.trades import services as trades_services
from apps.trades.models import TradeOffer

from .conftest import anunciar, logado

pytestmark = pytest.mark.django_db

mover = inventory_services.change_owner


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def test_a_guarda_do_mercado_esta_registrada() -> None:
    """Prova o `ready()` de `marketplace`: sem o registro, nada trava e o resto enganaria."""
    assert guards.listing_guard in inventory_services._MOVE_GUARDS


def test_item_anunciado_nao_muda_de_dono(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1)

    with pytest.raises(inventory_services.ItemLocked):
        mover(cena.a1.pk, from_owner=cena.ana, to_owner=cena.bruno)

    assert _dono(cena.a1) == cena.ana.pk
    assert MarketListing.objects.get(pk=anuncio.pk).status == ListingStatus.ACTIVE


def test_item_sem_anuncio_continua_livre(cena: SimpleNamespace) -> None:
    anunciar(cena.ana, cena.a1)  # só a1 está preso

    mover(cena.a2.pk, from_owner=cena.ana, to_owner=cena.bruno)

    assert _dono(cena.a2) == cena.bruno.pk


def test_cancelar_o_anuncio_libera_o_item(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1)
    services.cancel_listing(cena.ana, anuncio.pk)

    mover(cena.a1.pk, from_owner=cena.ana, to_owner=cena.bruno)

    assert _dono(cena.a1) == cena.bruno.pk


def test_o_cracha_do_proprio_anuncio_destrava_e_o_de_outro_nao(cena: SimpleNamespace) -> None:
    """`authorized_by` é o id do anúncio que o chamador executa; um crachá alheio não vale."""
    anuncio = anunciar(cena.ana, cena.a1)
    outro = anunciar(cena.ana, cena.a2)

    with pytest.raises(inventory_services.ItemLocked):
        mover(cena.a1.pk, from_owner=cena.ana, to_owner=cena.bruno, authorized_by=outro.pk)
    assert _dono(cena.a1) == cena.ana.pk

    mover(cena.a1.pk, from_owner=cena.ana, to_owner=cena.bruno, authorized_by=anuncio.pk)
    assert _dono(cena.a1) == cena.bruno.pk


def test_assert_movable_roda_as_guardas_sem_mover_o_item(cena: SimpleNamespace) -> None:
    """A porta que o mercado usa: expõe a guarda sem duplicar a regra de posse do inventory."""
    anuncio = anunciar(cena.ana, cena.a1)
    item = SkinInstance.objects.get(pk=cena.a1.pk)

    with pytest.raises(inventory_services.ItemLocked):
        inventory_services.assert_movable(item)
    assert _dono(cena.a1) == cena.ana.pk

    inventory_services.assert_movable(item, authorized_by=anuncio.pk)
    assert _dono(cena.a1) == cena.ana.pk  # anuncia não move: o dono continua o mesmo

    inventory_services.assert_movable(SkinInstance.objects.get(pk=cena.a2.pk))


def test_item_em_oferta_pendente_nao_pode_ser_anunciado(cena: SimpleNamespace) -> None:
    trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])

    with pytest.raises(services.ItemLocked):
        anunciar(cena.ana, cena.a1)

    assert MarketListing.objects.count() == 0
    assert _dono(cena.a1) == cena.ana.pk


def test_item_de_oferta_ja_resolvida_volta_a_poder_ser_anunciado(cena: SimpleNamespace) -> None:
    oferta = trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])
    trades_services.cancel_offer(cena.ana, oferta.pk)

    anuncio = anunciar(cena.ana, cena.a1)

    assert anuncio.status == ListingStatus.ACTIVE
    assert _dono(cena.a1) == cena.ana.pk


def test_item_alheio_em_oferta_pendente_da_404_e_nunca_item_locked(cena: SimpleNamespace) -> None:
    """A posse vence a guarda: `item_locked` revelaria a quem não é dono que o item existe."""
    trades_services.create_offer(cena.bruno, cena.ana, [cena.b1.pk], [cena.a1.pk])

    with pytest.raises(services.InstanceNotFound):
        anunciar(cena.ana, cena.b1)

    assert MarketListing.objects.count() == 0
    assert _dono(cena.b1) == cena.bruno.pk


@pytest.mark.parametrize("lado", ["oferecido", "pedido"])
def test_item_anunciado_nao_entra_numa_oferta_de_troca(cena: SimpleNamespace, lado: str) -> None:
    """O outro sentido da guarda: anúncio ativo recusa `create_offer`, dos dois lados da troca.

    Sem isto a oferta nasce pendente, o aceite sempre dá `item_locked` e o item anunciado fica
    preso pelo índice único das ofertas até alguém recusar (a oferta "zumbi"). O anúncio tem
    prioridade (decisão do dono, 2026-11-26): quem quer trocar cancela o anúncio antes.
    """
    if lado == "oferecido":
        anunciar(cena.ana, cena.a1)
    else:
        anunciar(cena.bruno, cena.b1)

    with pytest.raises(inventory_services.ItemLocked):
        trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])

    assert TradeOffer.objects.count() == 0
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)


def test_item_alheio_anunciado_continua_dando_o_erro_de_posse_da_troca(
    cena: SimpleNamespace,
) -> None:
    """A posse vence a guarda também em `trades`: o anúncio de carla não aparece num pedido."""
    anunciar(cena.carla, cena.c1)

    with pytest.raises(trades_services.ItemNotOwned):
        trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.c1.pk])

    assert TradeOffer.objects.count() == 0


def test_criar_oferta_com_item_anunciado_pela_api_da_409_item_locked(cena: SimpleNamespace) -> None:
    anunciar(cena.ana, cena.a1)
    corpo = {
        "recipient": cena.bruno.username,
        "offered": [str(cena.a1.pk)],
        "requested": [str(cena.b1.pk)],
    }

    resposta = logado(cena.ana).post(
        "/api/v1/trades/", corpo, format="json", headers={"Idempotency-Key": str(uuid.uuid4())}
    )

    assert resposta.status_code == 409, resposta.content
    assert resposta.json()["code"] == "item_locked"
    assert TradeOffer.objects.count() == 0


def test_item_locked_do_mercado_e_erro_de_mercado_com_codigo_estavel() -> None:
    assert issubclass(services.ItemLocked, services.MarketError)
    assert services.ItemLocked.code == "item_locked"
