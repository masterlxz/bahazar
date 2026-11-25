"""Leitura do catálogo de skins: busca, filtros, ordenação e facetas.

O catálogo é global (não pertence a usuário). Filtros são combinados com E.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.catalog.models import Skin

# Mapeamento de desgaste -> range de float (padrão CS2)
_WEAR_RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "Factory New": (Decimal("0.00"), Decimal("0.07")),
    "Minimal Wear": (Decimal("0.07"), Decimal("0.15")),
    "Field-Tested": (Decimal("0.15"), Decimal("0.38")),
    "Well-Worn": (Decimal("0.38"), Decimal("0.45")),
    "Battle-Scarred": (Decimal("0.45"), Decimal("1.00")),
}

# Campos de ordenação permitidos (lista branca)
_ORDER_FIELDS = {
    "name": "name",
    "price": "reference_price",
    "rarity": "rarity",
    "weapon": "weapon",
}
DEFAULT_ORDERING = "name"
ORDERING_CHOICES = [*_ORDER_FIELDS, *(f"-{chave}" for chave in _ORDER_FIELDS)]


def get(skin_id: UUID) -> Skin | None:
    """Busca uma skin ativa por UUID. Retorna None se não existe ou está inativa."""
    try:
        return Skin.objects.get(id=skin_id, active=True)
    except Skin.DoesNotExist:
        return None


def _wear_filter(qs: QuerySet[Skin], wears: list[str]) -> QuerySet[Skin]:
    """Filtra skins cujo range de float intersecta qualquer um dos desgastes pedidos."""
    if not wears:
        return qs
    condicao = None
    for wear in wears:
        if wear not in _WEAR_RANGES:
            continue
        inicio, fim = _WEAR_RANGES[wear]
        # A skin tem o desgaste se [min_float, max_float] intersecta [inicio, fim)
        # Ou seja: min_float < fim E max_float >= inicio
        from django.db.models import Q

        q = Q(min_float__lt=fim) & Q(max_float__gte=inicio)
        condicao = q if condicao is None else condicao | q
    return qs.filter(condicao) if condicao is not None else qs.none()


def _apply_ordering(qs: QuerySet[Skin], ordering: str) -> QuerySet[Skin]:
    """Aplica ordenação válida; levanta ValueError se inválida."""
    if ordering not in ORDERING_CHOICES:
        raise ValueError(f"ordenação desconhecida: {ordering}")
    campo = _ORDER_FIELDS[ordering.removeprefix("-")]
    prefixo = "-" if ordering.startswith("-") else ""
    # Desempate por id para paginação estável
    return qs.order_by(f"{prefixo}{campo}", "id")


def search(
    *,
    rarity: str | None = None,
    weapon: str | None = None,
    collection: str | None = None,
    wear: list[str] | None = None,
    q: str | None = None,
    ordering: str = DEFAULT_ORDERING,
) -> QuerySet[Skin]:
    """Busca skins ativas com filtros (E entre filtros), ordenação e desempate por id.

    Filtros:
    - rarity__iexact
    - weapon__iexact
    - collection__icontains
    - wear__in (lista de nomes de desgaste; usa range de float)
    - q -> name__icontains
    """
    qs = Skin.objects.filter(active=True)

    if rarity:
        qs = qs.filter(rarity__iexact=rarity)
    if weapon:
        qs = qs.filter(weapon__iexact=weapon)
    if collection:
        qs = qs.filter(collection__icontains=collection)
    if wear:
        qs = _wear_filter(qs, wear)
    if q:
        qs = qs.filter(name__icontains=q)

    return _apply_ordering(qs, ordering)


def facets(
    *,
    rarity: str | None = None,
    weapon: str | None = None,
    collection: str | None = None,
    wear: list[str] | None = None,
    q: str | None = None,
) -> dict[str, list[str]]:
    """Valores únicos para selects do frontend, respeitando filtros ativos."""
    qs = search(
        rarity=rarity,
        weapon=weapon,
        collection=collection,
        wear=wear,
        q=q,
        ordering="name",  # ordem estável para facetas
    )
    return {
        "rarity": sorted(qs.values_list("rarity", flat=True).distinct()),
        "weapon": sorted(qs.values_list("weapon", flat=True).distinct()),
        "collection": sorted(
            c for c in qs.values_list("collection", flat=True).distinct() if c
        ),
    }