"""Leitura do inventário, SEMPRE escopada a um dono (GUIDELINES 6).

Quem chama decide se o leitor pode ver aquele dono (`friends.selectors.can_view`); aqui o
escopo nunca vem de um parâmetro de consulta, só do `owner` já resolvido e autorizado.
"""

from django.db.models import QuerySet

from apps.accounts.models import User

from . import rules
from .models import SkinInstance

# O que o cliente pode pedir -> o campo real. Lista branca: nada de `order_by` com texto livre.
_ORDER_FIELDS = {
    "acquired_at": "acquired_at",
    "float_value": "float_value",
    "price": "skin__reference_price",
    "name": "skin__name",
}
DEFAULT_ORDERING = "-acquired_at"
ORDERING_CHOICES = [*_ORDER_FIELDS, *(f"-{chave}" for chave in _ORDER_FIELDS)]


def inventory_of(owner: User) -> QuerySet[SkinInstance]:
    """Os itens de `owner` que ainda estão em jogo (não consumidos), com a skin já carregada."""
    itens = SkinInstance.objects.filter(owner=owner, consumed_at__isnull=True)
    return itens.select_related("skin")


def _order_by(ordering: str) -> str:
    chave = ordering.removeprefix("-")
    if chave not in _ORDER_FIELDS:
        raise ValueError(f"ordenação desconhecida: {ordering}")
    return ("-" if ordering.startswith("-") else "") + _ORDER_FIELDS[chave]


def search(
    itens: QuerySet[SkinInstance],
    *,
    rarity: str | None = None,
    weapon: str | None = None,
    wear: str | None = None,
    q: str | None = None,
    ordering: str = DEFAULT_ORDERING,
) -> QuerySet[SkinInstance]:
    """Filtra (E entre os filtros) e ordena. O `id` é o desempate: sem ele a paginação repete."""
    if rarity:
        itens = itens.filter(skin__rarity__iexact=rarity)
    if weapon:
        itens = itens.filter(skin__weapon__iexact=weapon)
    if wear:
        inicio, fim = rules.wear_range(wear)
        itens = itens.filter(float_value__gte=inicio, float_value__lt=fim)
    if q:
        itens = itens.filter(skin__name__icontains=q)
    return itens.order_by(_order_by(ordering))
