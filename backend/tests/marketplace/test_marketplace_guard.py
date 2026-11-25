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
from apps.trades import services as trades_services

from .conftest import anunciar

pytestmark = pytest.mark.django_db

mover = inventory_services.change_owner


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def test_a_guarda_do_mercado_esta_registrada() -> None:
    """Prova o `ready()` de `marketplace`: sem o registro, nada trava e o resto enganaria."""
    from apps.marketplace import guards  # type: ignore[import-not-found, unused-ignore]

    assert guards.listing_guard in inventory_services._MOVE_GUARDS


def test_item_anunciado_nao_muda_de_dono(cena: SimpleNamespace) -> None:
    from apps.marketplace.models import (  # type: ignore[import-not-found, unused-ignore]
        ListingStatus,
        MarketListing,
    )

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
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]

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
        inventory_services.assert_movable(item)  # type: ignore[attr-defined, unused-ignore]
    assert _dono(cena.a1) == cena.ana.pk

    inventory_services.assert_movable(  # type: ignore[attr-defined, unused-ignore]
        item, authorized_by=anuncio.pk
    )
    assert _dono(cena.a1) == cena.ana.pk  # anuncia não move: o dono continua o mesmo

    inventory_services.assert_movable(  # type: ignore[attr-defined, unused-ignore]
        SkinInstance.objects.get(pk=cena.a2.pk)
    )


def test_item_em_oferta_pendente_nao_pode_ser_anunciado(cena: SimpleNamespace) -> None:
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import MarketListing  # type: ignore[import-not-found, unused-ignore]

    trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])

    with pytest.raises(services.ItemLocked):
        anunciar(cena.ana, cena.a1)

    assert MarketListing.objects.count() == 0
    assert _dono(cena.a1) == cena.ana.pk


def test_item_de_oferta_ja_resolvida_volta_a_poder_ser_anunciado(cena: SimpleNamespace) -> None:
    from apps.marketplace.models import ListingStatus  # type: ignore[import-not-found, unused-ignore]

    oferta = trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])
    trades_services.cancel_offer(cena.ana, oferta.pk)

    anuncio = anunciar(cena.ana, cena.a1)

    assert anuncio.status == ListingStatus.ACTIVE
    assert _dono(cena.a1) == cena.ana.pk


def test_item_alheio_em_oferta_pendente_da_404_e_nunca_item_locked(cena: SimpleNamespace) -> None:
    """A posse vence a guarda: `item_locked` revelaria a quem não é dono que o item existe."""
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import MarketListing  # type: ignore[import-not-found, unused-ignore]

    trades_services.create_offer(cena.bruno, cena.ana, [cena.b1.pk], [cena.a1.pk])

    with pytest.raises(services.InstanceNotFound):
        anunciar(cena.ana, cena.b1)

    assert MarketListing.objects.count() == 0
    assert _dono(cena.b1) == cena.bruno.pk


def test_item_locked_do_mercado_e_erro_de_mercado_com_codigo_estavel() -> None:
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]

    assert issubclass(services.ItemLocked, services.MarketError)
    assert services.ItemLocked.code == "item_locked"
