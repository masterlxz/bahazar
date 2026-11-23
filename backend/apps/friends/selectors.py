"""Leitura de amizades e a PERMISSÃO CENTRAL de visibilidade (R1, ADR 0010).

`can_view` é a única função que decide "este usuário pode ver os dados daquele?". Endpoints de
inventário, troca etc. a consultam em vez de comparar status de amizade. Quando ela nega, a view
responde **404**, nunca 403: 403 confirmaria que o recurso existe.
"""

from django.db.models import Q, QuerySet

from apps.accounts.models import User

from . import rules
from .models import Friendship, FriendshipStatus


def find_user(username: str) -> User | None:
    return User.objects.filter(username=username.strip().lower()).first()


def _par(a: User, b: User) -> Q:
    return Q(requester=a, addressee=b) | Q(requester=b, addressee=a)


def friendship_between(a: User, b: User) -> Friendship | None:
    return Friendship.objects.filter(_par(a, b)).first()


def can_view(viewer: User, owner: User) -> bool:
    """Dono ou amigo aceito. Pendente, bloqueado e sem relação negam."""
    if viewer.pk == owner.pk:
        return rules.can_view(same_user=True, friendship_status=None)
    relacao = friendship_between(viewer, owner)
    return rules.can_view(same_user=False, friendship_status=relacao.status if relacao else None)


def friends_of(user: User) -> QuerySet[User]:
    """Amigos aceitos de `user`, por nome."""
    enviados = Friendship.objects.filter(requester=user, status=FriendshipStatus.ACCEPTED).values(
        "addressee_id"
    )
    recebidos = Friendship.objects.filter(addressee=user, status=FriendshipStatus.ACCEPTED).values(
        "requester_id"
    )
    return User.objects.filter(Q(pk__in=enviados) | Q(pk__in=recebidos)).order_by("username")


def blocked_by(user: User) -> QuerySet[User]:
    """Quem `user` bloqueou, por nome. NUNCA quem bloqueou `user`: a linha de bloqueio guarda o
    bloqueador em `requester`, e filtrar o outro lado vazaria quem escondeu a conta."""
    bloqueados = Friendship.objects.filter(requester=user).values("addressee_id")
    return User.objects.filter(pk__in=bloqueados).order_by("username")


def received_requests(user: User) -> QuerySet[Friendship]:
    return (
        Friendship.objects.filter(addressee=user, status=FriendshipStatus.PENDING)
        .select_related("requester", "addressee")
        .order_by("-created_at", "id")
    )


def sent_requests(user: User) -> QuerySet[Friendship]:
    return (
        Friendship.objects.filter(requester=user, status=FriendshipStatus.PENDING)
        .select_related("requester", "addressee")
        .order_by("-created_at", "id")
    )
