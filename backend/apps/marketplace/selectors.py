"""Leitura dos anúncios globais do mercado."""

import uuid

from django.db.models import F, QuerySet

from .models import ListingStatus, MarketListing


def _vendaveis() -> QuerySet[MarketListing]:
    """Anúncios ativos cujo item ainda existe no jogo e continua do vendedor.

    Um `UPDATE` direto, o admin ou um trade-up que consome o item não passa pela guarda de
    movimento: o anúncio seguiria `active` no banco com um item que já não pode ser vendido. A
    vitrine esconde esse caso em vez de mostrá-lo; a compra (4.4) revalida sob trava mesmo assim.
    """
    return MarketListing.objects.filter(
        status=ListingStatus.ACTIVE,
        instance__consumed_at__isnull=True,
        instance__owner_id=F("seller_id"),
    )


def active_listings() -> QuerySet[MarketListing]:
    """Os anúncios ativos, dos mais novos aos mais antigos, com dados da vitrine já carregados.

    O id decrescente é o desempate: sem ele a paginação pode repetir ou pular anúncios criados
    no mesmo instante.
    """
    return _vendaveis().select_related("seller", "instance__skin").order_by("-created_at", "-id")


def active_listing(listing_id: uuid.UUID) -> MarketListing | None:
    """O anúncio ativo pedido, ou `None` se não existir ou já estiver fechado."""
    return _vendaveis().filter(pk=listing_id).select_related("seller", "instance__skin").first()


def has_active_listing(instance_id: uuid.UUID) -> bool:
    """A instância já tem algum anúncio ativo?"""
    return MarketListing.objects.filter(
        instance_id=instance_id,
        status=ListingStatus.ACTIVE,
    ).exists()
