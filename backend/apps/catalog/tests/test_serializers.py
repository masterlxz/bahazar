"""Serializers do catálogo: listagem (cards) e detalhe."""

from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIRequestFactory

from apps.catalog.models import Skin
from apps.catalog.serializers import SkinDetailSerializer, SkinListSerializer

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


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


class TestSkinListSerializer:
    """Serialização para cards: só o essencial."""

    def test_campos_essenciais_estao_presentes(self) -> None:
        s = _skin()
        data = SkinListSerializer(s).data

        assert set(data.keys()) == {
            "id",
            "name",
            "weapon",
            "rarity",
            "collection",
            "reference_price",
            "min_float",
            "max_float",
        }
        assert data["name"] == "AK-47 | Redline"
        assert data["weapon"] == "AK-47"
        assert data["rarity"] == "Classified"
        assert data["collection"] == "The Chroma Collection"
        assert data["reference_price"] == 1234
        assert data["min_float"] == "0.070000000"
        assert data["max_float"] == "0.800000000"

    def test_collection_vazia_vai_como_string_vazia(self) -> None:
        s = _skin(collection="")
        data = SkinListSerializer(s).data
        assert data["collection"] == ""

    def test_preco_em_centavos_nao_vaza_como_float(self) -> None:
        s = _skin(reference_price=9999)
        data = SkinListSerializer(s).data
        assert isinstance(data["reference_price"], int)
        assert data["reference_price"] == 9999


class TestSkinDetailSerializer:
    """Serialização completa: todos os campos do modelo."""

    def test_todos_os_campos_estao_presentes(self) -> None:
        s = _skin()
        data = SkinDetailSerializer(s).data

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

    def test_image_url_e_source_vao_como_estao_no_banco(self) -> None:
        s = _skin(image_url="https://example.com/skin.png", image_source="skinport")
        data = SkinDetailSerializer(s).data
        assert data["image_url"] == "https://example.com/skin.png"
        assert data["image_source"] == "skinport"

    def test_campos_sao_read_only(self) -> None:
        s = _skin()
        serializer = SkinDetailSerializer(s, data={"name": "Hacked"})
        assert not serializer.is_valid()  # read_only_fields = todos