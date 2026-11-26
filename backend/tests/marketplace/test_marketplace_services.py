"""Serviço do mercado: o estado gravado, a tradução do índice único e o fechamento do anúncio."""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from django.utils import timezone

from apps.inventory.models import SkinInstance

from .conftest import anunciar, nova_chave

pytestmark = pytest.mark.django_db


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def test_criar_grava_o_anuncio_ativo_e_nao_mexe_no_item(cena: SimpleNamespace) -> None:
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import (  # type: ignore[import-not-found, unused-ignore]
        ListingStatus,
        MarketListing,
    )

    saida = services.create_listing(cena.ana, cena.a1.pk, 700, idempotency_key=nova_chave())

    gravado = MarketListing.objects.get(pk=saida.body["id"])
    assert (gravado.seller_id, gravado.instance_id, gravado.price) == (
        cena.ana.pk,
        cena.a1.pk,
        700,
    )
    assert (gravado.status, gravado.closed_at) == (ListingStatus.ACTIVE, None)
    assert gravado.created_at is not None
    assert _dono(cena.a1) == cena.ana.pk


def test_cancelar_grava_o_estado_terminal_e_o_instante_do_fechamento(cena: SimpleNamespace) -> None:
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import (  # type: ignore[import-not-found, unused-ignore]
        ListingStatus,
        MarketListing,
    )

    anuncio = anunciar(cena.ana, cena.a1)
    antes = timezone.now()

    cancelado = services.cancel_listing(cena.ana, anuncio.pk, idempotency_key=nova_chave())

    gravado = MarketListing.objects.get(pk=anuncio.pk)
    assert cancelado.body["id"] == str(anuncio.pk)
    assert gravado.status == ListingStatus.CANCELLED
    assert gravado.closed_at is not None
    assert gravado.closed_at >= antes
    assert gravado.price == anuncio.price
    assert _dono(cena.a1) == cena.ana.pk


def test_o_indice_unico_do_banco_fecha_a_corrida_que_o_python_deixou_passar(
    cena: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com a checagem em Python desligada, o INSERT esbarra no índice parcial e vira o erro certo.

    Prova que a garantia "uma instância, um anúncio ativo" também está no banco, não só no
    serviço: sem o índice, dois anúncios ativos entrariam e a vitrine ficaria ambígua.
    """
    from apps.inventory import services as inventory_services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace import selectors, services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import (  # type: ignore[import-not-found, unused-ignore]
        ListingStatus,
        MarketListing,
    )

    monkeypatch.setattr(selectors, "has_active_listing", lambda instance_id: False)
    # Also disable the move guards (listing_guard) so the test reaches the database INSERT
    monkeypatch.setattr(inventory_services, "_MOVE_GUARDS", [])
    anunciar(cena.ana, cena.a1)

    with pytest.raises(services.ItemAlreadyListed):
        anunciar(cena.ana, cena.a1, price=999)

    assert MarketListing.objects.filter(instance=cena.a1, status=ListingStatus.ACTIVE).count() == 1


def test_o_indice_unico_nao_atrapalha_um_anuncio_novo_depois_do_cancelamento(
    cena: SimpleNamespace,
) -> None:
    """O índice é parcial: anúncio cancelado não ocupa a vaga do item."""
    from apps.marketplace import services  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import (  # type: ignore[import-not-found, unused-ignore]
        ListingStatus,
        MarketListing,
    )

    primeiro = anunciar(cena.ana, cena.a1)
    services.cancel_listing(cena.ana, primeiro.pk, idempotency_key=nova_chave())

    segundo = anunciar(cena.ana, cena.a1, price=50)

    assert MarketListing.objects.filter(instance=cena.a1).count() == 2
    assert MarketListing.objects.get(pk=segundo.pk).status == ListingStatus.ACTIVE
    assert MarketListing.objects.get(pk=primeiro.pk).status == ListingStatus.CANCELLED
