"""Única porta de escrita de itens (GUIDELINES 2): ninguém cria `SkinInstance` por fora daqui."""

import uuid
from collections.abc import Callable
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


class NotOwner(InventoryError):
    code = "not_owner"
    message = "O item não pertence a quem o está entregando."


class ConsumedInstance(InventoryError):
    code = "consumed_instance"
    message = "O item já saiu do jogo."


class ItemLocked(InventoryError):
    code = "item_locked"
    message = "O item está travado por outra operação e não pode mudar de dono."


# Guarda de movimentação: um módulo (hoje `trades`) pode travar um item sem que este núcleo o
# conheça. Recebe a instância (já travada, dentro da transação) e o `authorized_by` que o chamador
# passou ao `change_owner` (opaco aqui); levanta `ItemLocked` para recusar a troca de dono.
MoveGuard = Callable[[SkinInstance, uuid.UUID | None], None]
_MOVE_GUARDS: list[MoveGuard] = []


def register_move_guard(guard: MoveGuard) -> None:
    """Registra uma guarda de movimentação (idempotente: a mesma função entra uma só vez).

    Cada módulo registra a sua em `AppConfig.ready()`. Com 2 ou mais módulos, todas rodam, na
    ordem do registro, e a primeira que levantar `ItemLocked` desfaz a troca.
    """
    if guard not in _MOVE_GUARDS:
        _MOVE_GUARDS.append(guard)


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
    if not rules.float_in_range(float_value, skin.min_float, skin.max_float):
        raise InvalidFloat
    with transaction.atomic():
        return SkinInstance.objects.create(
            owner=owner,
            skin=skin,
            float_value=float_value,
            acquired_via=acquired_via,
            acquired_ref_id=ref_id,
        )


def change_owner(
    instance_id: uuid.UUID,
    *,
    from_owner: User,
    to_owner: User,
    authorized_by: uuid.UUID | None = None,
) -> SkinInstance:
    """Passa o item de `from_owner` para `to_owner`: a ÚNICA porta que muda o dono (GUIDELINES 2).

    Só o dono muda: id, float, skin e origem ficam como estão (nada é criado nem apagado).
    Trava a linha e confere dono e consumo já sob a trava. Quem move vários itens (a troca)
    trava todos antes, em ordem de UUID, para nunca cruzar esperas com outra operação.

    Depois do dono e do consumo (assim `ItemLocked` nunca revela a um não dono que o item existe
    e está em uso), roda as guardas registradas (`register_move_guard`): se alguma levantar
    `ItemLocked`, o dono não muda. `authorized_by` identifica a operação que está movendo o item
    (para `trades`, o id da própria oferta que está sendo aceita) e só é repassado às guardas:
    sem ele, um item travado por qualquer módulo não anda.

    ATENÇÃO a quem chamar FORA de `trades` (mercado, trade-up): `change_owner` sozinho trava só
    a instância e toma KEY SHARE na linha do NOVO dono (a FK do `UPDATE`). `trades.create_offer`
    e `accept_offer` seguram os jogadores com FOR UPDATE e DEPOIS as instâncias; quem travar a
    instância antes dos jogadores pode formar um ciclo de espera com elas. Trave antes os
    jogadores envolvidos, por id, e só então as instâncias, por UUID.
    """
    with transaction.atomic():
        instancia = SkinInstance.objects.select_for_update().filter(pk=instance_id).first()
        if instancia is None or instancia.owner_id != from_owner.pk:
            raise NotOwner
        if instancia.consumed_at is not None:
            raise ConsumedInstance
        for guarda in _MOVE_GUARDS:
            guarda(instancia, authorized_by)
        instancia.owner = to_owner
        instancia.save(update_fields=["owner"])
        return instancia
