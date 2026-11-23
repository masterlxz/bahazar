"""Casca transacional de amizades: trava o par, aplica as regras puras e grava.

Toda operação sobre um par trava as DUAS linhas de usuário em ordem de id. Sem isso, ana->bruno
e bruno->ana simultâneos travariam em ordem oposta (deadlock), e aceitar x bloquear poderiam
passar uma pela outra.
"""

import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User

from . import rules, selectors
from .models import Friendship, FriendshipStatus


class FriendshipError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "friendship_error"
    message = "Operação não permitida."


class Unavailable(FriendshipError):
    """Mesma resposta para inexistente, auto-pedido e bloqueado (anti-enumeração)."""

    code = "friendship_unavailable"
    message = "Não foi possível enviar o pedido a este jogador."


class AlreadyPending(FriendshipError):
    code = "already_pending"
    message = "Já existe um pedido pendente entre vocês."


class AlreadyFriends(FriendshipError):
    code = "already_friends"
    message = "Vocês já são amigos."


class NotFound(FriendshipError):
    """O alvo não existe ou o chamador não tem direito sobre ele: a view responde 404."""

    code = "not_found"
    message = "Não encontrado."


_FALHAS_DO_PEDIDO: dict[str, type[FriendshipError]] = {
    rules.ALREADY_PENDING: AlreadyPending,
    rules.ALREADY_FRIENDS: AlreadyFriends,
    rules.UNAVAILABLE: Unavailable,
}


def _travar(*ids: uuid.UUID) -> None:
    list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def _relacao(a: uuid.UUID, b: uuid.UUID) -> Friendship | None:
    return Friendship.objects.filter(
        Q(requester_id=a, addressee_id=b) | Q(requester_id=b, addressee_id=a)
    ).first()


def send_request(requester: User, username: str) -> Friendship:
    alvo = selectors.find_user(username)
    if alvo is None or alvo.pk == requester.pk:
        raise Unavailable
    with transaction.atomic():
        _travar(requester.pk, alvo.pk)
        existente = _relacao(requester.pk, alvo.pk)
        resultado = rules.request_outcome(
            (existente.status, existente.requester_id == requester.pk) if existente else None
        )
        if resultado != rules.CREATE:
            raise _FALHAS_DO_PEDIDO[resultado]
        return Friendship.objects.create(
            requester=requester, addressee=alvo, status=FriendshipStatus.PENDING
        )


def _pedido_pendente_para(user: User, friendship_id: uuid.UUID) -> Friendship:
    """Trava o par e devolve o pedido pendente cujo destinatário é `user`.

    Lê uma vez sem trava para descobrir o par, trava, e RELÊ: entre as duas leituras um
    bloqueio pode ter reescrito a linha.
    """
    previa = Friendship.objects.filter(pk=friendship_id, addressee=user).first()
    if previa is None:
        raise NotFound
    _travar(previa.requester_id, user.pk)
    pedido = Friendship.objects.filter(
        pk=friendship_id, addressee=user, status=FriendshipStatus.PENDING
    ).first()
    if pedido is None:
        raise NotFound
    return pedido


def accept_request(user: User, friendship_id: uuid.UUID) -> Friendship:
    with transaction.atomic():
        pedido = _pedido_pendente_para(user, friendship_id)
        pedido.status = FriendshipStatus.ACCEPTED
        pedido.responded_at = timezone.now()
        pedido.save(update_fields=["status", "responded_at"])
    return pedido


def decline_request(user: User, friendship_id: uuid.UUID) -> None:
    with transaction.atomic():
        _pedido_pendente_para(user, friendship_id).delete()


def _alvo(username: str, user: User) -> User:
    alvo = selectors.find_user(username)
    if alvo is None or alvo.pk == user.pk:
        raise NotFound
    return alvo


def remove_friend(user: User, username: str) -> None:
    alvo = _alvo(username, user)
    with transaction.atomic():
        _travar(user.pk, alvo.pk)
        amizade = _relacao(user.pk, alvo.pk)
        if amizade is None or amizade.status != FriendshipStatus.ACCEPTED:
            raise NotFound
        amizade.delete()


def block(user: User, username: str) -> None:
    """Bloqueia `alvo`: derruba amizade ou pedido e grava `user` como bloqueador.

    Idempotente. Se o alvo já tinha bloqueado `user`, o bloqueio dele é mantido (o de `user`
    não o substitui), para que só ele possa desfazê-lo.
    """
    alvo = _alvo(username, user)
    with transaction.atomic():
        _travar(user.pk, alvo.pk)
        existente = _relacao(user.pk, alvo.pk)
        if existente is None:
            Friendship.objects.create(
                requester=user,
                addressee=alvo,
                status=FriendshipStatus.BLOCKED,
                responded_at=timezone.now(),
            )
        elif existente.status != FriendshipStatus.BLOCKED:
            existente.requester = user
            existente.addressee = alvo
            existente.status = FriendshipStatus.BLOCKED
            existente.responded_at = timezone.now()
            existente.save(update_fields=["requester", "addressee", "status", "responded_at"])


def unblock(user: User, username: str) -> None:
    """Só o bloqueador desfaz. Não restaura a amizade que existia."""
    alvo = _alvo(username, user)
    with transaction.atomic():
        _travar(user.pk, alvo.pk)
        existente = _relacao(user.pk, alvo.pk)
        if (
            existente is None
            or existente.status != FriendshipStatus.BLOCKED
            or existente.requester_id != user.pk
        ):
            raise NotFound
        existente.delete()
