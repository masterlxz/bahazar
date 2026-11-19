"""Leitura de salas. TODA consulta de sala para uma view passa por aqui, escopada ao usuário.

É o equivalente do "manager escopado" de SEGURANCA §3: sem RLS, um filtro esquecido vazaria
salas alheias, então a view nunca usa `Room.objects` solto.
"""

from django.db.models import OuterRef, QuerySet, Subquery

from apps.accounts.models import User

from .models import MemberStatus, Room, RoomMember


def rooms_for_user(user: User) -> QuerySet[Room]:
    """Salas ativas onde `user` é membro ativo, com o papel dele em `my_role`."""
    papel = RoomMember.objects.filter(
        room=OuterRef("pk"), user=user, status=MemberStatus.ACTIVE
    ).values("role")[:1]
    return (
        Room.objects.filter(
            archived_at__isnull=True, members__status=MemberStatus.ACTIVE
        )
        .annotate(my_role=Subquery(papel))
        .order_by("-created_at", "id")
    )
