"""Serializers do catálogo de skins."""

from rest_framework import serializers

from apps.catalog.models import Skin


class SkinListSerializer(serializers.ModelSerializer):
    """Serialização para listagem (cards): apenas campos essenciais."""

    class Meta:
        model = Skin
        fields = (
            "id",
            "name",
            "weapon",
            "rarity",
            "collection",
            "reference_price",
            "min_float",
            "max_float",
        )
        read_only_fields = fields


class SkinDetailSerializer(serializers.ModelSerializer):
    """Serialização completa: todos os campos do modelo."""

    class Meta:
        model = Skin
        fields = (
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
        )
        read_only_fields = fields
