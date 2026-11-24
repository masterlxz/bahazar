"""Única porta de escrita de itens (GUIDELINES 2): ninguém cria `SkinInstance` por fora daqui."""

import uuid
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import Skin

from . import rules
from .models import AcquiredVia, SkinInstance


class InventoryError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "inventory_error"
    message = "Operação não permitida."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class InvalidFloat(InventoryError):
    code = "invalid_float"
    message = "O float está fora da faixa da skin."


class InactiveSkin(InventoryError):
    code = "inactive_skin"
    message = "A skin está inativa e não pode ser entregue."


def create_instance(
    owner: User,
    skin: Skin,
    float_value: Decimal,
    *,
    acquired_via: str,
    ref_id: uuid.UUID | None = None,
) -> SkinInstance:
    """Cria um item para `owner`. O float precisa estar na faixa da skin (o banco também barra)."""
    if acquired_via not in AcquiredVia.values:
        raise InventoryError(f"Origem desconhecida: {acquired_via}")
    if not skin.active:
        raise InactiveSkin
    if not rules.float_in_range(float_value, Decimal(0), Decimal(1)):
        raise InvalidFloat
    float_value = float_value.quantize(rules.FLOAT_STEP)  # confere o valor que será gravado
    with transaction.atomic():
        return SkinInstance.objects.create(
            owner=owner,
            skin=skin,
            float_value=float_value,
            acquired_via=acquired_via,
            acquired_ref_id=ref_id,
        )
