from rest_framework import serializers

from apps.catalog.models import Skin

from . import rules, selectors
from .models import SkinInstance

MAX_PAGE_SIZE = 100


class InventoryQuerySerializer(serializers.Serializer):
    """A query do inventário. Valor inválido vira 400; campo ausente vale o padrão."""

    rarity = serializers.CharField(required=False, allow_blank=True, max_length=64)
    weapon = serializers.CharField(required=False, allow_blank=True, max_length=64)
    wear = serializers.ChoiceField(choices=rules.WEARS, required=False, allow_blank=True)
    q = serializers.CharField(required=False, allow_blank=True, max_length=50)
    ordering = serializers.ChoiceField(
        choices=selectors.ORDERING_CHOICES, required=False, default=selectors.DEFAULT_ORDERING
    )
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=MAX_PAGE_SIZE)


class SkinSummarySerializer(serializers.ModelSerializer):
    """A skin de um item: o que o jogador precisa para reconhecê-la, sem dado interno."""

    class Meta:
        model = Skin
        fields = ("id", "name", "weapon", "rarity", "collection")
        read_only_fields = fields


class InventoryItemSerializer(serializers.ModelSerializer):
    """Um item do inventário, igual para o dono e para um amigo.

    O desgaste é derivado do float; o preço é o de referência da skin, em centavos de USD.
    Sem origem da aquisição, sem dono e sem estado de consumo: dado interno não sai por aqui.
    """

    skin = SkinSummarySerializer(read_only=True)
    wear = serializers.SerializerMethodField()
    reference_price = serializers.IntegerField(source="skin.reference_price", read_only=True)

    class Meta:
        model = SkinInstance
        fields = ("id", "skin", "float_value", "wear", "reference_price", "acquired_via")
        read_only_fields = fields

    def get_wear(self, item: SkinInstance) -> str:
        return rules.wear_for(item.float_value)
