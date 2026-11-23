"""Leitura de salas. TODA consulta de sala para uma view passa por aqui, escopada ao usuário.

É o equivalente do "manager escopado" de SEGURANCA §3: sem RLS, um filtro esquecido vazaria
salas alheias, então a view nunca usa `Room.objects` solto.
"""

from django.db.models import OuterRef, QuerySet, Subquery

from apps.accounts.models import User

from .models import MemberStatus, Room, RoomInvite, RoomMember


def rooms_for_user(user: User) -> QuerySet[Room]:
    """Salas ativas onde `user` é membro ativo, com o papel dele em `my_role`."""
    papel = RoomMember.objects.filter(
        room=OuterRef("pk"), user=user, status=MemberStatus.ACTIVE
    ).values("role")[:1]
    return (
        Room.objects.filter(
            archived_at__isnull=True, members__user=user, members__status=MemberStatus.ACTIVE
        )
        .annotate(my_role=Subquery(papel))
        .order_by("-created_at", "id")
    )


def members_of(room: Room) -> QuerySet[RoomMember]:
    """Membros ATIVOS da sala, por ordem de entrada. Quem saiu ou foi banido não aparece.

    A VIEW só chama isto com uma `room` obtida por `rooms_for_user`, ou seja, depois de conferir
    que quem pergunta é membro ativo (senão o 404 de "sala inexistente" já saiu).
    """
    return RoomMember.objects.filter(room=room).select_related("user").order_by("joined_at", "id")


def invites_of_room(room: Room) -> QuerySet[RoomInvite]:
    """Convites de uma sala, sem o código (que nem existe no banco). A VIEW só chama isto depois
    de conferir que quem pergunta é dono ou administrador da `room`, obtida por `rooms_for_user`.
    """
    return RoomInvite.objects.filter(room=room).order_by("-created_at", "id")
