"""Leitura dos anúncios globais do mercado."""

import uuid

from django.db.models import QuerySet

from .models import ListingStatus, MarketListing


def active_listings() -> QuerySet[MarketListing]:
    """Os anúncios ativos, dos mais novos aos mais antigos, com dados da vitrine já carregados.

    O id decrescente é o desempate: sem ele a paginação pode repetir ou pular anúncios criados
    no mesmo instante.
    """
    return (
        MarketListing.objects.filter(status=ListingStatus.ACTIVE)
        .select_related("seller", "instance__skin")
        .order_by("-created_at", "-id")
    )


def active_listing(listing_id: uuid.UUID) -> MarketListing | None:
    """O anúncio ativo pedido, ou `None` se não existir ou já estiver fechado."""
    return (
        MarketListing.objects.filter(pk=listing_id, status=ListingStatus.ACTIVE)
        .select_related("seller", "instance__skin")
        .first()
    )


def has_active_listing(instance_id: uuid.UUID) -> bool:
    """A instância já tem algum anúncio ativo?"""
    return MarketListing.objects.filter(
        instance_id=instance_id,
        status=ListingStatus.ACTIVE,
    ).exists()
