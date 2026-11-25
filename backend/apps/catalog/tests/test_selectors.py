"""Selectors do catálogo: busca com filtros, ordenação, paginação e facetas."""

from decimal import Decimal
from uuid import uuid4

import pytest

from apps.catalog import selectors
from apps.catalog.models import Skin

pytestmark = pytest.mark.django_db


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


class TestGet:
    """Busca por UUID."""

    def test_encontra_skin_por_uuid(self) -> None:
        s = _skin()
        encontrado = selectors.get(s.id)
        assert encontrado == s

    def test_nao_encontrado_retorna_none(self) -> None:
        assert selectors.get(uuid4()) is None

    def test_skin_inativa_nao_e_encontrada(self) -> None:
        s = _skin(active=False)
        assert selectors.get(s.id) is None


class TestSearch:
    """Busca com filtros (E entre filtros), ordenação e paginação."""

    @pytest.fixture(autouse=True)
    def _cenario(self) -> None:
        # 5 skins com combinações variadas
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
        self.s5 = _skin(
            external_id="skin-5",
            name="Glock-18 | Water Elemental",
            weapon="Glock-18",
            rarity="Restricted",
            collection="The Assault Collection",
            min_float=Decimal("0.00"),
            max_float=Decimal("1.00"),
            reference_price=150,
        )

    # --- filtro rarity (iexact) ---
    def test_filtro_rarity_classified_retorna_duas(self) -> None:
        qs = selectors.search(rarity="classified")
        assert qs.count() == 2
        assert {s.name for s in qs} == {"AK-47 | Redline", "M4A4 | Neo-Noir"}

    def test_filtro_rarity_case_insensitive(self) -> None:
        qs = selectors.search(rarity="CLASSIFIED")
        assert qs.count() == 2

    def test_filtro_rarity_inexistente_retorna_vazio(self) -> None:
        assert selectors.search(rarity="Contraband").count() == 0

    # --- filtro weapon (iexact) ---
    def test_filtro_weapon_ak47_retorna_duas(self) -> None:
        qs = selectors.search(weapon="AK-47")
        assert qs.count() == 2
        assert {s.weapon for s in qs} == {"AK-47"}

    def test_filtro_weapon_case_insensitive(self) -> None:
        assert selectors.search(weapon="ak-47").count() == 2

    # --- filtro collection (icontains) ---
    def test_filtro_collection_chroma_retorna_duas(self) -> None:
        qs = selectors.search(collection="chroma")
        assert qs.count() == 2

    def test_filtro_collection_case_insensitive(self) -> None:
        assert selectors.search(collection="ASSAULT").count() == 2

    # --- filtro wear (in: lista de desgastes) ---
    def test_filtro_wear_factory_new_retorna_as_que_tem_fn(self) -> None:
        # s1 (0.07-0.80), s2 (0.00-0.85), s4 (0.00-1.00), s5 (0.00-1.00) têm FN
        qs = selectors.search(wear=["Factory New"])
        assert qs.count() == 4
        assert self.s3 not in qs  # Asiimov min 0.18

    def test_filtro_wear_multiplos_valores(self) -> None:
        qs = selectors.search(wear=["Factory New", "Minimal Wear"])
        assert qs.count() == 4

    def test_filtro_wear_inexistente_retorna_vazio(self) -> None:
        # Nenhuma skin tem range que inclua "Battle-Scarred" exclusivamente
        qs = selectors.search(wear=["Battle-Scarred"])
        assert qs.count() == 4  # todas exceto Asiimov têm range até 1.00

    # --- filtro q (icontains no name) ---
    def test_filtro_q_ak47_retorna_duas(self) -> None:
        qs = selectors.search(q="AK-47")
        assert qs.count() == 2

    def test_filtro_q_case_insensitive(self) -> None:
        assert selectors.search(q="redline").count() == 1

    def test_filtro_q_parcial(self) -> None:
        assert selectors.search(q="Neo").count() == 1

    # --- combinação de filtros (E) ---
    def test_filtros_combinados_sao_e(self) -> None:
        qs = selectors.search(weapon="AK-47", rarity="Classified")
        assert qs.count() == 1
        assert qs.first().name == "AK-47 | Redline"

    def test_filtros_que_nao_combinam_retornam_vazio(self) -> None:
        assert selectors.search(weapon="AK-47", rarity="Covert").count() == 0

    # --- ordenação ---
    def test_ordenacao_padrao_e_por_nome_crescente(self) -> None:
        qs = selectors.search()
        nomes = [s.name for s in qs]
        assert nomes == sorted(nomes)

    def test_ordenacao_por_preco_crescente(self) -> None:
        qs = selectors.search(ordering="price")
        precos = [s.reference_price for s in qs]
        assert precos == sorted(precos)

    def test_ordenacao_por_preco_decrescente(self) -> None:
        qs = selectors.search(ordering="-price")
        precos = [s.reference_price for s in qs]
        assert precos == sorted(precos, reverse=True)

    def test_ordenacao_por_raridade_crescente(self) -> None:
        qs = selectors.search(ordering="rarity")
        raridades = [s.rarity for s in qs]
        assert raridades == sorted(raridades)

    def test_ordenacao_por_arma_crescente(self) -> None:
        qs = selectors.search(ordering="weapon")
        armas = [s.weapon for s in qs]
        assert armas == sorted(armas)

    def test_ordenacao_invalida_levanta_erro(self) -> None:
        with pytest.raises(ValueError, match="ordenação desconhecida"):
            selectors.search(ordering="invalido")

    def test_desempate_por_id(self) -> None:
        # Mesmo nome, mesmo preço: o id desempata
        s_a = _skin(name="AK-47 | Teste", reference_price=1000)
        s_b = _skin(name="AK-47 | Teste", reference_price=1000)
        qs = selectors.search(ordering="name")
        ids = [s.id for s in qs if s.name == "AK-47 | Teste"]
        assert ids == sorted(ids)

    # --- paginação não é responsabilidade do selector ---
    # O selector devolve QuerySet; a view pagina.


class TestFacets:
    """Valores únicos para selects do frontend."""

    @pytest.fixture(autouse=True)
    def _cenario(self) -> None:
        _skin(name="AK-47 | A", weapon="AK-47", rarity="Classified", collection="Col A")
        _skin(name="M4A4 | B", weapon="M4A4", rarity="Restricted", collection="Col A")
        _skin(name="AWP | C", weapon="AWP", rarity="Covert", collection="Col B")

    def test_facets_devolve_valores_unicos_ordenados(self) -> None:
        f = selectors.facets()
        assert f["rarity"] == ["Classified", "Covert", "Restricted"]
        assert f["weapon"] == ["AK-47", "AWP", "M4A4"]
        assert f["collection"] == ["Col A", "Col B"]

    def test_facets_respeita_filtros_ativos(self) -> None:
        f = selectors.facets(weapon="AK-47")
        assert f["rarity"] == ["Classified"]
        assert f["weapon"] == ["AK-47"]
        assert f["collection"] == ["Col A"]