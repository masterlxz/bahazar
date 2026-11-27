"""Leitura de amizades e a PERMISSÃO CENTRAL de visibilidade (R1, ADR 0010).

`can_view` é a única função que decide "este usuário pode ver os dados daquele?". Endpoints de
inventário, troca etc. a consultam em vez de comparar status de amizade. Quando ela nega, a view
responde **404**, nunca 403: 403 confirmaria que o recurso existe.
"""

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.accounts.models import User

from . import rules
from .models import Friendship, FriendshipStatus


def find_user(username: str) -> User | None:
    return User.objects.filter(username=username.strip().lower()).first()


def _par(a: User, b: User) -> Q:
    return Q(requester=a, addressee=b) | Q(requester=b, addressee=a)


def friendship_between(a: User, b: User) -> Friendship | None:
    return Friendship.objects.filter(_par(a, b)).first()


def pair_is_blocked(a_field: str, b_field: str) -> Exists:
    """Subconsulta "há bloqueio, em qualquer direção, entre estes dois jogadores?".

    `a_field` e `b_field` nomeiam, na consulta de fora, as duas colunas que apontam para os
    jogadores (por exemplo `"proposer"` e `"recipient"` de uma oferta). Quem lê dados de um par
    usa `.filter(~pair_is_blocked(...))` para esconder o par bloqueado: a regra "bloqueio" fica
    aqui, em `friends`, e quem consome não compara status de amizade. Só o bloqueio esconde; um
    ex-amigo (sem linha) e um pedido pendente não.
    """
    bloqueios = Friendship.objects.exclude(status=FriendshipStatus.ACCEPTED).filter(
        Q(requester=OuterRef(a_field), addressee=OuterRef(b_field))
        | Q(requester=OuterRef(b_field), addressee=OuterRef(a_field))
    )
    return Exists(bloqueios)


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
    bloqueados = Friendship.objects.filter(requester=user, status=FriendshipStatus.BLOCKED).values(
        "addressee_id"
    )
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
