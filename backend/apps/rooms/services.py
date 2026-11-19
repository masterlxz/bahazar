"""Casca transacional de salas: carrega, trava, aplica as regras puras e grava."""

import uuid

from django.db import transaction

from apps.accounts.models import User

from . import rules
from .models import MemberStatus, Role, Room, RoomMember


class RoomError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "room_error"
    message = "Operação não permitida."


class RoomLimitReached(RoomError):
    code = "room_limit_reached"
    message = f"Você já é dono de {rules.MAX_ROOMS_AS_OWNER} salas."


class OwnerCannotLeave(RoomError):
    code = "owner_cannot_leave"
    message = "O dono não pode sair da própria sala."


def create_room(user: User, name: str) -> Room:
    """Cria a sala e torna `user` o dono. O limite é checado sob trava da linha do usuário,
    para duas criações simultâneas não furarem o teto."""
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        owned = Room.objects.filter(owner=user, archived_at__isnull=True).count()
        if not rules.can_create_room(owned):
            raise RoomLimitReached
        room = Room.objects.create(name=name, owner=user)
        RoomMember.objects.create(room=room, user=user, role=Role.OWNER, status=MemberStatus.ACTIVE)
    return room


def leave_room(user: User, room_id: uuid.UUID) -> None:
    """Marca a saída de `user`. Revalida o pertencimento dentro da transação.

    Levanta `RoomMember.DoesNotExist` se `user` não é membro ativo de uma sala ativa.
    """
    with transaction.atomic():
        member = RoomMember.objects.select_for_update(of=("self",)).get(
            room_id=room_id,
            user=user,
            status=MemberStatus.ACTIVE,
            room__archived_at__isnull=True,
        )
        if not rules.can_leave(member.role):
            raise OwnerCannotLeave
        member.status = MemberStatus.LEFT
        member.save(update_fields=["status"])
