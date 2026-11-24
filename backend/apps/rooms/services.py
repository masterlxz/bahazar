"""Casca transacional de salas: carrega, trava, aplica as regras puras e grava."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User

from . import rules
from .models import MemberStatus, Role, Room, RoomInvite, RoomMember


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


# --- convites (SEGURANCA §5) ---


class InviteNotFound(RoomError):
    """Código desconhecido, ou de quem foi banido: a view responde 404, sem dizer qual."""

    code = "invite_not_found"
    message = "Convite não encontrado."


class NotRoomAdmin(RoomError):
    code = "not_room_admin"
    message = "Só o dono ou um administrador pode gerenciar convites."


class InvalidInvitePolicy(RoomError):
    code = "invalid_invite_policy"
    message = f"Use de 1 a {rules.MAX_INVITE_DAYS} dias e de 1 a {rules.MAX_INVITE_USES} usos."


class InviteLimitReached(RoomError):
    code = "invite_limit_reached"
    message = f"A sala já tem {rules.MAX_ACTIVE_INVITES} convites ativos."


class InviteExpired(RoomError):
    code = "invite_expired"
    message = "Este convite expirou."


class InviteRevoked(RoomError):
    code = "invite_revoked"
    message = "Este convite foi revogado."


class InviteExhausted(RoomError):
    code = "invite_exhausted"
    message = "Este convite já foi usado o máximo de vezes."


class RoomFull(RoomError):
    code = "room_full"
    message = "A sala está cheia."


class RoomArchived(RoomError):
    code = "room_archived"
    message = "A sala foi arquivada."


_ERRO_DO_ESTADO: dict[str, type[RoomError]] = {
    "revoked": InviteRevoked,
    "expired": InviteExpired,
    "exhausted": InviteExhausted,
}


def _hash(codigo: str) -> bytes:
    return hashlib.sha256(codigo.encode()).digest()


def _admin_da_sala(user: User, room_id: uuid.UUID, *, travar_sala: bool) -> Room:
    """Confere que `user` é dono ou administrador ativo e devolve a sala.

    `travar_sala` só quando a operação não trava convites: o resgate trava convite e depois sala,
    então quem trava sala e depois convite (revogar) abriria um deadlock.

    Levanta `RoomMember.DoesNotExist` se não é membro ativo de uma sala ativa (a view responde
    404) e `NotRoomAdmin` se é membro comum (403).
    """
    membro = RoomMember.objects.get(
        room_id=room_id, user=user, status=MemberStatus.ACTIVE, room__archived_at__isnull=True
    )
    if not rules.is_room_admin(membro.role):
        raise NotRoomAdmin
    consulta = Room.objects.select_for_update() if travar_sala else Room.objects.all()
    return consulta.get(pk=room_id)


def create_invite(
    user: User,
    room_id: uuid.UUID,
    expires_in_days: int | None = None,
    max_uses: int | None = None,
    now: datetime | None = None,
) -> tuple[RoomInvite, str]:
    """Cria um convite e devolve `(convite, código)`. O código só existe neste retorno."""
    dias = rules.DEFAULT_INVITE_DAYS if expires_in_days is None else expires_in_days
    usos = rules.DEFAULT_INVITE_USES if max_uses is None else max_uses
    if not rules.invite_policy_valid(dias, usos):
        raise InvalidInvitePolicy
    agora = now or timezone.now()
    with transaction.atomic():
        # A trava da sala serializa a contagem do teto; criar não trava convite existente.
        sala = _admin_da_sala(user, room_id, travar_sala=True)
        ativos = RoomInvite.objects.filter(
            room=sala, revoked_at__isnull=True, expires_at__gt=agora, uses__lt=F("max_uses")
        ).count()
        if ativos >= rules.MAX_ACTIVE_INVITES:
            raise InviteLimitReached
        codigo = secrets.token_urlsafe(16)  # 128 bits
        convite = RoomInvite.objects.create(
            room=sala,
            created_by=user,
            code_hash=_hash(codigo),
            expires_at=agora + timedelta(days=dias),
            max_uses=usos,
        )
    return convite, codigo


def revoke_invite(user: User, room_id: uuid.UUID, invite_id: uuid.UUID) -> None:
    """Revoga (idempotente). Trava a linha do convite, a mesma do resgate."""
    with transaction.atomic():
        _admin_da_sala(user, room_id, travar_sala=False)
        convite = (
            RoomInvite.objects.select_for_update().filter(pk=invite_id, room_id=room_id).first()
        )
        if convite is None:
            raise InviteNotFound
        if convite.revoked_at is None:
            convite.revoked_at = timezone.now()
            convite.save(update_fields=["revoked_at"])


def redeem_invite(user: User, code: str, now: datetime | None = None) -> Room:
    """Entra na sala pelo código. Ordem das travas: convite, depois sala (nunca o inverso).

    Já ser membro ativo é sucesso sem gastar uso (idempotente). Quem saiu volta pela mesma linha
    de `RoomMember`. Convite inutilizável levanta o erro do motivo; código desconhecido e
    banido levantam `InviteNotFound`.
    """
    agora = now or timezone.now()
    with transaction.atomic():
        convite = RoomInvite.objects.select_for_update().filter(code_hash=_hash(code)).first()
        if convite is None:
            raise InviteNotFound
        sala = Room.objects.select_for_update().get(pk=convite.room_id)
        membro = RoomMember.objects.filter(room=sala, user=user).first()
        if membro is not None and membro.status == MemberStatus.BANNED:
            raise InviteNotFound
        if sala.archived_at is not None:
            raise RoomArchived
        if membro is not None and membro.status == MemberStatus.ACTIVE:
            return sala
        estado = rules.invite_state(
            now=agora,
            expires_at=convite.expires_at,
            revoked=convite.revoked_at is not None,
            uses=convite.uses,
            max_uses=convite.max_uses,
        )
        if estado != "ok":
            raise _ERRO_DO_ESTADO[estado]
        ativos = RoomMember.objects.filter(room=sala, status=MemberStatus.ACTIVE).count()
        if rules.room_is_full(ativos, sala.max_members):
            raise RoomFull
        if membro is None:
            RoomMember.objects.create(
                room=sala, user=user, role=Role.MEMBER, status=MemberStatus.ACTIVE, joined_at=agora
            )
        else:
            membro.status = MemberStatus.ACTIVE
            membro.role = Role.MEMBER
            membro.joined_at = agora
            membro.save(update_fields=["status", "role", "joined_at"])
        convite.uses += 1
        convite.save(update_fields=["uses"])
    return sala
