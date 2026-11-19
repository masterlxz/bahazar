from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from . import rules


def _papel(obj: Any) -> str | None:
    """Papel do usuário na sala, anotado por `selectors.rooms_for_user` em `my_role`."""
    papel: str | None = getattr(obj, "my_role", None)
    return papel


class IsRoomMember(BasePermission):
    """Só quem é membro ativo da sala. Sem papel anotado, nega (nunca presume)."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return _papel(obj) is not None


class IsRoomAdmin(BasePermission):
    """Só dono ou administrador da sala."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return rules.is_room_admin(_papel(obj))
