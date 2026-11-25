"""Testes de integração das views do catálogo: list, retrieve, facets."""

from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Skin

pytestmark = pytest.mark.django_db

CATALOG_URL = "/api/v1/catalog/skins/"
FACETS_URL = "/api/v1/catalog/skins/facets/"


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


class TestSkinListView:
    """GET /api/v1/catalog/skins/"""

    @pytest.fixture(autouse=True)
    def _cenario(self) -> None:
        self.s1 = _skin(
            external_id="skin-1",
            name="AK-47 | Redline",
            weapon="AK-47",
            rarity="Classified",
            collection="The Chroma Collection",
            reference_price=1234,
        )
        self.s2 = _skin(
            external_id="skin-2",
            name="M4A4 | Neo-Noir",
            weapon="M4A4",
            rarity="Classified",
            collection="The Chroma Collection",
            reference_price=800,
        )
        self.s3 = _skin(
            external_id="skin-3",
            name="AWP | Asiimov",
            weapon="AWP",
            rarity="Covert",
            collection="The Phoenix Collection",
            reference_price=5000,
        )

    def test_list_devolve_200_e_paginacao(self) -> None:
        resp = APIClient().get(CATALOG_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        assert len(data["results"]) == 3
        assert "next" in data and "previous" in data

    def test_list_apenas_skins_ativas(self) -> None:
        _skin(name="Inativa", active=False)
        resp = APIClient().get(CATALOG_URL)
        assert resp.json()["count"] == 3

    def test_list_ordenacao_padrao_e_nome_crescente(self) -> None:
        data = APIClient().get(CATALOG_URL).json()
        nomes = [r["name"] for r in data["results"]]
        assert nomes == sorted(nomes)


class TestSkinDetailView:
    """GET /api/v1/catalog/skins/<uuid>/"""

    @pytest.fixture(autouse=True)
    def _cenario(self) -> None:
        self.skin = _skin(
            name="AK-47 | Redline",
            image_url="https://example.com/skin.png",
            image_source="skinport",
        )

    def test_retrieve_devolve_todos_os_campos(self) -> None:
        url = f"{CATALOG_URL}{self.skin.id}/"
        resp = APIClient().get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {
            "id",
            "external_id",
            "name",
            "weapon",
            "rarity",
            "collection",
            "min_float",
            "max_float",
            "reference_price",
            "image_url",
            "image_source",
            "active",
        }
        assert data["image_url"] == "https://example.com/skin.png"
        assert data["image_source"] == "skinport"

    def test_retrieve_404_para_uuid_inexistente(self) -> None:
        url = f"{CATALOG_URL}{uuid4()}/"
        resp = APIClient().get(url)
        assert resp.status_code == 404
        assert resp.json() == {"code": "not_found", "message": "Não encontrado."}

    def test_retrieve_404_para_skin_inativa(self) -> None:
        inativa = _skin(name="Inativa", active=False)
        url = f"{CATALOG_URL}{inativa.id}/"
        resp = APIClient().get(url)
        assert resp.status_code == 404
        assert resp.json() == {"code": "not_found", "message": "Não encontrado."}


class TestFacetsView:
    """GET /api/v1/catalog/skins/facets/"""

    @pytest.fixture(autouse=True)
    def _cenario(self) -> None:
        _skin(name="AK-47 | A", weapon="AK-47", rarity="Classified", collection="Col A")
        _skin(name="M4A4 | B", weapon="M4A4", rarity="Restricted", collection="Col A")
        _skin(name="AWP | C", weapon="AWP", rarity="Covert", collection="Col B")

    def test_facets_devolve_valores_unicos_ordenados(self) -> None:
        resp = APIClient().get(FACETS_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rarity"] == ["Classified", "Covert", "Restricted"]
        assert data["weapon"] == ["AK-47", "AWP", "M4A4"]
        assert data["collection"] == ["Col A", "Col B"]

    def test_facets_respeita_filtros_ativos(self) -> None:
        resp = APIClient().get(FACETS_URL, {"weapon": "AK-47"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["rarity"] == ["Classified"]
        assert data["weapon"] == ["AK-47"]
        assert data["collection"] == ["Col A"]

    def test_facets_com_filtro_que_nao_combina_retorna_listas_vazias(self) -> None:
        resp = APIClient().get(FACETS_URL, {"rarity": "Contraband"})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"rarity": [], "weapon": [], "collection": []}


class TestMetodosNaoPermitidos:
    """A API é somente leitura: POST, PUT, PATCH, DELETE dão 405."""

    @pytest.fixture(autouse=True)
    def _skin(self) -> Skin:
        return _skin()

    @pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
    def test_list_nao_aceita_escrita(self, metodo: str) -> None:
        resp = getattr(APIClient(), metodo)(CATALOG_URL, {})
        assert resp.status_code == 405

    @pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
    def test_detail_nao_aceita_escrita(self, _skin: Skin, metodo: str) -> None:
        url = f"{CATALOG_URL}{_skin.id}/"
        resp = getattr(APIClient(), metodo)(url, {})
        assert resp.status_code == 405

    @pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
    def test_facets_nao_aceita_escrita(self, metodo: str) -> None:
        resp = getattr(APIClient(), metodo)(FACETS_URL, {})
        assert resp.status_code == 405


class TestAutenticacaoNaoObrigatoria:
    """O catálogo é público: não exige autenticação."""

    def test_list_sem_auth(self) -> None:
        resp = APIClient().get(CATALOG_URL)
        assert resp.status_code == 200

    def test_detail_sem_auth(self) -> None:
        s = _skin()
        resp = APIClient().get(f"{CATALOG_URL}{s.id}/")
        assert resp.status_code == 200

    def test_facets_sem_auth(self) -> None:
        resp = APIClient().get(FACETS_URL)
        assert resp.status_code == 200
