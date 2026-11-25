"""Testes de integração dos filtros do catálogo via API (sem django-filter)."""

from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Skin

pytestmark = pytest.mark.django_db

CATALOG_URL = "/api/v1/catalog/skins/"


def _skin(**campos) -> Skin:
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


class TestCatalogFiltersAPI:
    """Filtros expostos pela API REST."""

    @pytest.fixture(autouse=True)
    def _cenario(self) -> None:
        self.s1 = _skin(
            external_id="skin-1",
            name="AK-47 | Redline",
            weapon="AK-47",
            rarity="Classified",
            collection="The Chroma Collection",
            min_float=Decimal("0.07"),
            max_float=Decimal("0.80"),
            reference_price=1234,
        )
        self.s2 = _skin(
            external_id="skin-2",
            name="M4A4 | Neo-Noir",
            weapon="M4A4",
            rarity="Classified",
            collection="The Chroma Collection",
            min_float=Decimal("0.00"),
            max_float=Decimal("0.85"),
            reference_price=800,
        )
        self.s3 = _skin(
            external_id="skin-3",
            name="AWP | Asiimov",
            weapon="AWP",
            rarity="Covert",
            collection="The Phoenix Collection",
            min_float=Decimal("0.18"),
            max_float=Decimal("1.00"),
            reference_price=5000,
        )
        self.s4 = _skin(
            external_id="skin-4",
            name="AK-47 | Blue Laminate",
            weapon="AK-47",
            rarity="Restricted",
            collection="The Assault Collection",
            min_float=Decimal("0.00"),
            max_float=Decimal("1.00"),
            reference_price=300,
        )

    def _get(self, params: dict | None = None) -> dict:
        resp = APIClient().get(CATALOG_URL, params or {})
        assert resp.status_code == 200, resp.content
        return resp.json()

    # --- rarity ---
    def test_filtro_rarity_classified(self) -> None:
        data = self._get({"rarity": "classified"})
        assert data["count"] == 2
        assert {r["name"] for r in data["results"]} == {"AK-47 | Redline", "M4A4 | Neo-Noir"}

    def test_filtro_rarity_case_insensitive(self) -> None:
        assert self._get({"rarity": "CLASSIFIED"})["count"] == 2
        assert self._get({"rarity": "Classified"})["count"] == 2

    # --- weapon ---
    def test_filtro_weapon_ak47(self) -> None:
        data = self._get({"weapon": "AK-47"})
        assert data["count"] == 2
        assert all(r["weapon"] == "AK-47" for r in data["results"])

    def test_filtro_weapon_case_insensitive(self) -> None:
        assert self._get({"weapon": "ak-47"})["count"] == 2

    # --- collection ---
    def test_filtro_collection_chroma(self) -> None:
        data = self._get({"collection": "chroma"})
        assert data["count"] == 2

    def test_filtro_collection_case_insensitive(self) -> None:
        assert self._get({"collection": "ASSAULT"})["count"] == 1

    # --- wear ---
    def test_filtro_wear_factory_new(self) -> None:
        data = self._get({"wear": "Factory New"})
        # s1, s2, s4 têm range incluindo FN (0.00-0.07)
        assert data["count"] == 3
        assert self.s3.name not in [r["name"] for r in data["results"]]

    def test_filtro_wear_multiplos_valores_virgula(self) -> None:
        data = self._get({"wear": "Factory New,Minimal Wear"})
        assert data["count"] == 3

    # --- q (busca textual) ---
    def test_filtro_q_ak47(self) -> None:
        data = self._get({"q": "AK-47"})
        assert data["count"] == 2

    def test_filtro_q_case_insensitive(self) -> None:
        assert self._get({"q": "redline"})["count"] == 1

    # --- combinação (E) ---
    def test_filtros_combinados(self) -> None:
        data = self._get({"weapon": "AK-47", "rarity": "Classified"})
        assert data["count"] == 1
        assert data["results"][0]["name"] == "AK-47 | Redline"

    # --- ordenação ---
    def test_ordenacao_preco_crescente(self) -> None:
        data = self._get({"ordering": "price"})
        precos = [r["reference_price"] for r in data["results"]]
        assert precos == sorted(precos)

    def test_ordenacao_preco_decrescente(self) -> None:
        data = self._get({"ordering": "-price"})
        precos = [r["reference_price"] for r in data["results"]]
        assert precos == sorted(precos, reverse=True)

    def test_ordenacao_nome_crescente(self) -> None:
        data = self._get({"ordering": "name"})
        nomes = [r["name"] for r in data["results"]]
        assert nomes == sorted(nomes)

    def test_ordenacao_raridade_crescente(self) -> None:
        data = self._get({"ordering": "rarity"})
        raridades = [r["rarity"] for r in data["results"]]
        assert raridades == sorted(raridades)

    def test_ordenacao_arma_crescente(self) -> None:
        data = self._get({"ordering": "weapon"})
        armas = [r["weapon"] for r in data["results"]]
        assert armas == sorted(armas)

    def test_ordenacao_invalida_vira_400(self) -> None:
        resp = APIClient().get(CATALOG_URL, {"ordering": "invalido"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "invalid_ordering"

    # --- paginação ---
    def test_paginacao_padrao(self) -> None:
        data = self._get()
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data

    def test_page_size_personalizado(self) -> None:
        data = self._get({"page_size": "2"})
        assert len(data["results"]) <= 2
        assert data["count"] == 4

    def test_page_size_limite_maximo(self) -> None:
        # Cria mais skins para testar o limite
        for i in range(10):
            _skin(external_id=f"skin-extra-{i}", name=f"Extra {i}")
        data = self._get({"page_size": "1000"})  # acima do max
        assert len(data["results"]) <= 100  # MAX_PAGE_SIZE

    # --- campos da resposta (list serializer) ---
    def test_resposta_list_tem_campos_essenciais(self) -> None:
        data = self._get()
        skin = data["results"][0]
        assert set(skin.keys()) == {
            "id",
            "name",
            "weapon",
            "rarity",
            "collection",
            "reference_price",
            "min_float",
            "max_float",
        }
        assert isinstance(skin["reference_price"], int)
        assert "image_url" not in skin
        assert "external_id" not in skin
