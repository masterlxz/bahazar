import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Visibility(models.TextChoices):
    PRIVATE = "private", "Privada"
    PUBLIC = "public", "Pública"  # reservado: o jogo só tem salas privadas por enquanto


class Role(models.TextChoices):
    OWNER = "owner", "Dono"
    ADMIN = "admin", "Administrador"
    MEMBER = "member", "Membro"


class MemberStatus(models.TextChoices):
    ACTIVE = "active", "Ativo"
    LEFT = "left", "Saiu"
    BANNED = "banned", "Banido"


class Room(models.Model):
    """Uma sala é uma economia independente (MODELO-DE-DADOS §3.1).

    Os campos econômicos (`starting_balance`, `market_fee_bps`) chegam com a PR 2.2, quando a
    carteira passa a usá-los.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_rooms"
    )
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    max_members = models.PositiveSmallIntegerField(default=20)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(visibility__in=Visibility.values), name="room_visibility_valid"
            ),
            models.CheckConstraint(condition=Q(max_members__gte=1), name="room_max_members_min"),
        ]

    def __str__(self) -> str:
        return self.name


class RoomMember(models.Model):
    """Pertencimento de um usuário a uma sala. É a base de toda a autorização por sala."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="room_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    status = models.CharField(max_length=10, choices=MemberStatus.choices)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["room", "user"], name="room_member_unique_user"),
            # Exatamente um dono ativo por sala. Parcial: quem saiu não bloqueia um novo dono.
            models.UniqueConstraint(
                fields=["room"],
                condition=Q(role="owner", status="active"),
                name="room_member_one_active_owner",
            ),
            models.CheckConstraint(
                condition=Q(role__in=Role.values), name="room_member_role_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=MemberStatus.values), name="room_member_status_valid"
            ),
        ]
        indexes = [models.Index(fields=["user", "room"], name="room_member_user_room_idx")]

    def __str__(self) -> str:
        return f"{self.user_id} em {self.room_id} ({self.role})"


class RoomInvite(models.Model):
    """Convite de entrada na sala (SEGURANCA §5). O código em claro NUNCA é gravado.

    `code_hash` é o sha256 do código (128 bits aleatórios). Revogar preenche `revoked_at` e não
    apaga a linha (auditoria).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="invites")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="room_invites_created"
    )
    code_hash = models.BinaryField(max_length=32, unique=True)
    expires_at = models.DateTimeField()
    max_uses = models.PositiveSmallIntegerField()
    uses = models.PositiveSmallIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(uses__gte=0), name="room_invite_uses_nonneg"),
            models.CheckConstraint(
                condition=Q(uses__lte=F("max_uses")), name="room_invite_uses_within_max"
            ),
            models.CheckConstraint(condition=Q(max_uses__gte=1), name="room_invite_max_uses_min"),
        ]
        indexes = [models.Index(fields=["room", "revoked_at"], name="room_invite_room_revoked_idx")]

    def __str__(self) -> str:
        return f"convite {self.id} da sala {self.room_id}"
