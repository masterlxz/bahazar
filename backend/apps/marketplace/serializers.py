"""Entrada e saída da API do mercado."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from rest_framework import serializers

from apps.accounts.models import User
from apps.catalog.models import Skin
from apps.inventory.models import SkinInstance

from . import rules
from .models import MarketListing

_CAMPOS_DO_CORPO = frozenset({"instance_id", "price"})
_CORPO_INVALIDO = "O corpo precisa ser um objeto JSON."
_INSTANCE_INVALIDO = "O identificador de um item é inválido."
_PRECO_INVALIDO = "O preço deve ser um inteiro positivo em centavos."


class InvalidInput(Exception):
    """O corpo da requisição não tem a forma esperada. `code` é estável."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CreateListingInput:
    """Corpo validado de `POST /listings/`."""

    instance_id: uuid.UUID
    price: int


def parse_create_body(dados: object) -> CreateListingInput:
    """Confere o corpo de `POST /listings/` e devolve os valores já normalizados."""
    if not isinstance(dados, Mapping):
        raise InvalidInput("invalid_body", _CORPO_INVALIDO)
    if set(dados) - _CAMPOS_DO_CORPO:
        raise InvalidInput("invalid_body", "O corpo tem campos que a API não conhece.")

    instance_bruto = dados.get("instance_id")
    if not isinstance(instance_bruto, str):
        raise InvalidInput("invalid_body", _INSTANCE_INVALIDO)
    try:
        instance_id = uuid.UUID(instance_bruto)
    except ValueError:
        raise InvalidInput("invalid_body", _INSTANCE_INVALIDO) from None

    price = dados.get("price")
    if not rules.price_is_valid(price):
        raise InvalidInput("invalid_price", _PRECO_INVALIDO)
    return CreateListingInput(instance_id=instance_id, price=price)


class SellerSerializer(serializers.ModelSerializer):
    """O vendedor do anúncio: somente id e nome de usuário."""

    class Meta:
        model = User
        fields = ("id", "username")
        read_only_fields = fields


class ListingSkinSerializer(serializers.ModelSerializer):
    """A skin do item anunciado, sem dados que a vitrine não precisa."""

    class Meta:
        model = Skin
        fields = ("id", "name", "weapon", "rarity")
        read_only_fields = fields


class ListingInstanceSerializer(serializers.ModelSerializer):
    """O item anunciado: id, float e a skin que o identifica."""

    id = serializers.UUIDField(read_only=True)
    skin = ListingSkinSerializer(read_only=True)
    float_value = serializers.DecimalField(
        max_digits=10,
        decimal_places=9,
        read_only=True,
    )

    class Meta:
        model = SkinInstance
        fields = ("id", "float_value", "skin")
        read_only_fields = fields


class ListingSerializer(serializers.ModelSerializer):
    """O anúncio como a API o mostra."""

    seller = SellerSerializer(read_only=True)
    instance = ListingInstanceSerializer(read_only=True)

    class Meta:
        model = MarketListing
        fields = ("id", "price", "status", "created_at", "closed_at", "seller", "instance")
        read_only_fields = fields
