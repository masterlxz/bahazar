"""Entrada e saída da API das trocas.

A entrada (`parse_create_body`) é a fronteira de confiança: o corpo vem do cliente e é conferido
AQUI, antes de qualquer consulta. A saída é a oferta com os dois jogadores (só o que
`FriendSerializer` já expõe) e os itens como o inventário os mostra, sem dado interno.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from rest_framework import serializers

from apps.friends.serializers import FriendSerializer
from apps.inventory import rules as inventory_rules
from apps.inventory.serializers import SkinSummarySerializer

from . import rules
from .models import TradeOffer, TradeOfferItem

_USERNAME_MAX = 20  # o mesmo teto de `friends`
_CAMPOS_DO_CORPO = frozenset({"recipient", "offered", "requested"})
_ITEM_INVALIDO = "O identificador de um item é inválido."
_RECIPIENT_INVALIDO = "Informe o nome de usuário do destinatário."


class InvalidInput(Exception):
    """O corpo da requisição não tem a forma esperada. `code` é estável, como o dos serviços."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CreateInput:
    """Corpo validado de `POST /trades/`: o nome já sem espaços e em minúsculas."""

    recipient: str
    offered: list[uuid.UUID]
    requested: list[uuid.UUID]


def _recipient(valor: object) -> str:
    if not isinstance(valor, str):
        raise InvalidInput("invalid_recipient", _RECIPIENT_INVALIDO)
    nome = valor.strip().lower()
    # `isprintable` recusa o NUL e outros controles, que o PostgreSQL não aceita em texto.
    if not 0 < len(nome) <= _USERNAME_MAX or not nome.isprintable():
        raise InvalidInput("invalid_recipient", _RECIPIENT_INVALIDO)
    return nome


def _item_ids(valor: object, campo: str) -> list[uuid.UUID]:
    """Uma lista de UUID. O teto é conferido ANTES de iterar: lista gigante não vira trabalho."""
    if not isinstance(valor, list):
        raise InvalidInput("invalid_items", f"`{campo}` precisa ser uma lista de itens.")
    if len(valor) > rules.MAX_ITEMS_PER_SIDE:
        raise InvalidInput("too_many_items", f"`{campo}` tem itens demais.")
    ids: list[uuid.UUID] = []
    for bruto in valor:
        if not isinstance(bruto, str):
            raise InvalidInput("invalid_item_id", _ITEM_INVALIDO)
        try:
            ids.append(uuid.UUID(bruto))
        except ValueError:
            raise InvalidInput("invalid_item_id", _ITEM_INVALIDO) from None
    return ids


def parse_create_body(dados: object) -> CreateInput:
    """Confere o corpo de `POST /trades/` e devolve os ids já como `uuid.UUID`.

    Listas vazias passam daqui: "lado vazio" é regra de negócio e o serviço a recusa.
    """
    if not isinstance(dados, Mapping):
        raise InvalidInput("invalid_body", "O corpo precisa ser um objeto JSON.")
    desconhecidos = set(dados) - _CAMPOS_DO_CORPO
    if desconhecidos:
        # Campo que a API não define nunca é ignorado em silêncio (SEGURANCA 8): o cliente
        # que manda `price` ou `proposer` acredita que isso vale para alguma coisa.
        raise InvalidInput("invalid_body", "O corpo tem campos que a API não conhece.")
    return CreateInput(
        recipient=_recipient(dados.get("recipient")),
        offered=_item_ids(dados.get("offered"), "offered"),
        requested=_item_ids(dados.get("requested"), "requested"),
    )


class TradeItemSerializer(serializers.ModelSerializer):
    """Um item da oferta: a instância (id, float, desgaste) e a skin, como no inventário.

    Sem dono, sem origem da aquisição, sem `active` e sem estado de consumo.
    """

    id = serializers.UUIDField(source="instance_id", read_only=True)
    skin = SkinSummarySerializer(source="instance.skin", read_only=True)
    float_value = serializers.DecimalField(
        max_digits=10, decimal_places=9, source="instance.float_value", read_only=True
    )
    wear = serializers.SerializerMethodField()
    reference_price = serializers.IntegerField(
        source="instance.skin.reference_price", read_only=True
    )

    class Meta:
        model = TradeOfferItem
        fields = ("side", "id", "skin", "float_value", "wear", "reference_price")
        read_only_fields = fields

    def get_wear(self, item: TradeOfferItem) -> str:
        return inventory_rules.wear_for(item.instance.float_value)


class TradeOfferSerializer(serializers.ModelSerializer):
    """A oferta com os dois jogadores e os itens. Chamar `selectors.load_items` antes."""

    proposer = FriendSerializer(read_only=True)
    recipient = FriendSerializer(read_only=True)
    items = TradeItemSerializer(many=True, read_only=True)

    class Meta:
        model = TradeOffer
        fields = ("id", "status", "created_at", "resolved_at", "proposer", "recipient", "items")
        read_only_fields = fields
