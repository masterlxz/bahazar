"""Leitura dos anúncios globais do mercado."""

import uuid
from collections.abc import Iterable

from django.db.models import F, QuerySet

from .models import ListingStatus, MarketListing


def _vendaveis() -> QuerySet[MarketListing]:
    """Anúncios ativos cujo item ainda existe no jogo e continua do vendedor.

    Um `UPDATE` direto, o admin ou um trade-up que consome o item não passa pela guarda de
    movimento: o anúncio seguiria `active` no banco com um item que já não pode ser vendido. A
    vitrine esconde esse caso em vez de mostrá-lo; a compra (4.4) revalida sob trava mesmo assim.

    O vendedor desativado (`is_active=False`, J4) também some: o anúncio dele nunca poderia ser
    comprado, e a compra dá o mesmo 404 de anúncio inexistente, para ninguém distinguir uma conta
    desativada de um anúncio que não existe. É o ponto único da vitrine e do detalhe.
    """
    return MarketListing.objects.filter(
        status=ListingStatus.ACTIVE,
        seller__is_active=True,
        instance__consumed_at__isnull=True,
        instance__owner_id=F("seller_id"),
    )


def active_listings(hide_sellers: Iterable[uuid.UUID] = ()) -> QuerySet[MarketListing]:
    """Os anúncios ativos, dos mais novos aos mais antigos, com dados da vitrine já carregados.

    `hide_sellers` são os vendedores que quem olha bloqueou (ADR 0017): a vista dele não os
    mostra. Quem foi bloqueado não passa nada aqui e vê a vitrine inteira.

    O id decrescente é o desempate: sem ele a paginação pode repetir ou pular anúncios criados
    no mesmo instante.
    """
    return (
        _vendaveis()
        .exclude(seller_id__in=list(hide_sellers))
        .select_related("seller", "instance__skin")
        .order_by("-created_at", "-id")
    )


def active_listing(
    listing_id: uuid.UUID, hide_sellers: Iterable[uuid.UUID] = ()
) -> MarketListing | None:
    """O anúncio ativo pedido, ou `None` se não existir ou já estiver fechado.

    Anúncio de um vendedor em `hide_sellers` também dá `None`: o mesmo 404, para o detalhe não
    revelar o que a lista esconde.
    """
    return (
        MarketListing.objects.filter(status=ListingStatus.ACTIVE)
        .exclude(seller_id__in=list(hide_sellers))
        .filter(pk=listing_id)
        .select_related("seller", "instance__skin")
        .first()
    )


def is_hidden(listing_id: uuid.UUID, hide_sellers: Iterable[uuid.UUID]) -> bool:
    """O anúncio é de um vendedor que quem olha bloqueou, em qualquer estado?

    A compra usa isto para dar o mesmo 404 do detalhe: sem olhar o estado, porque um anúncio
    escondido não pode revelar se está ativo, vendido ou cancelado.
    """
    return MarketListing.objects.filter(pk=listing_id, seller_id__in=list(hide_sellers)).exists()


def has_active_listing(instance_id: uuid.UUID) -> bool:
    """A instância já tem algum anúncio ativo?"""
    return MarketListing.objects.filter(
        instance_id=instance_id,
        status=ListingStatus.ACTIVE,
    ).exists()
