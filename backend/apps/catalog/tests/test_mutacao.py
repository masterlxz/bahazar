"""Teste de mutação deliberada: remover um filtro derruba o teste correspondente.

Este arquivo NÃO testa comportamento correto; ele garante que os testes de filtro
realmente exercitam o código de filtro. Se alguém remover um filtro do selector,
o teste correspondente em test_filters.py DEVE falhar.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from apps.catalog import selectors
from apps.catalog.models import Skin

pytestmark = pytest.mark.django_db


def _skin(**campos: object) -> Skin:
    base = {
        "external_id": f"skin-{uuid4().hex[:8]}",
        "weapon": "AK-47",
        "name": "AK-47 | Redline",
        "collection": "The Chroma Collection",
        "rarity": "Classified",
        "min_float": Decimal("0.07"),
        "max_float": Decimal("0.80"),
        "reference_price": 1234,
        "image_url": "",
        "image_source": "none",
        "active": True,
    }
    base.update(campos)
    return Skin.objects.create(**base)


class TestMutacaoFiltros:
    """Cada teste aqui assume que UM filtro específico existe no selector.
    Se o filtro for removido, o teste falha (o filtro não faz efeito)."""

    def test_filtro_rarity_existe_no_selector(self) -> None:
        _skin(name="A", rarity="Classified")
        _skin(name="B", rarity="Restricted")
        qs = selectors.search(rarity="classified")
        # Se o filtro rarity for removido, viriam 2 em vez de 1
        assert qs.count() == 1
        first = qs.first()
        assert first is not None
        assert first.rarity == "Classified"

    def test_filtro_weapon_existe_no_selector(self) -> None:
        _skin(name="A", weapon="AK-47")
        _skin(name="B", weapon="M4A4")
        qs = selectors.search(weapon="AK-47")
        assert qs.count() == 1
        first = qs.first()
        assert first is not None
        assert first.weapon == "AK-47"

    def test_filtro_collection_existe_no_selector(self) -> None:
        _skin(name="A", collection="Col A")
        _skin(name="B", collection="Col B")
        qs = selectors.search(collection="col a")
        assert qs.count() == 1
        first = qs.first()
        assert first is not None
        assert first.collection == "Col A"

    def test_filtro_wear_existe_no_selector(self) -> None:
        # FN range: 0.00-0.07
        _skin(name="A", min_float=Decimal("0.00"), max_float=Decimal("0.07"))
        # MW range: 0.07-0.15
        _skin(name="B", min_float=Decimal("0.07"), max_float=Decimal("0.15"))
        qs = selectors.search(wear=["Factory New"])
        assert qs.count() == 1
        first = qs.first()
        assert first is not None
        assert first.name == "A"

    def test_filtro_q_existe_no_selector(self) -> None:
        _skin(name="AK-47 | Redline")
        _skin(name="M4A4 | Neo-Noir")
        qs = selectors.search(q="AK-47")
        assert qs.count() == 1
        first = qs.first()
        assert first is not None
        assert "AK-47" in first.name

    def test_ordenacao_existe_no_selector(self) -> None:
        _skin(name="Zebra", reference_price=100)
        _skin(name="Alpha", reference_price=200)
        qs = selectors.search(ordering="price")
        precos = [s.reference_price for s in qs]
        # Se a ordenação for removida, a ordem seria por nome (padrão): 200, 100
        assert precos == [100, 200]
