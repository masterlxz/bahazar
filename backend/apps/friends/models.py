import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Greatest, Least


class FriendshipStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACCEPTED = "accepted", "Aceita"
    BLOCKED = "blocked", "Bloqueada"


class Friendship(models.Model):
    """Relação entre dois jogadores. Uma linha por par, qualquer que seja a direção.

    - `pending`: `requester` pediu e `addressee` ainda não respondeu.
    - `accepted`: amigos (a direção só registra quem pediu).
    - `blocked`: `requester` é **quem bloqueou**; a linha é reescrita ao bloquear.
    Recusar e remover apagam a linha: não existe estado "recusado".
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="friendships_sent"
    )
    addressee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="friendships_received"
    )
    status = models.CharField(max_length=10, choices=FriendshipStatus.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(requester=F("addressee")), name="friendship_no_self"
            ),
            models.CheckConstraint(
                condition=Q(status__in=FriendshipStatus.values), name="friendship_status_valid"
            ),
            # Um registro por par NÃO ORDENADO: (a, b) e (b, a) caem na mesma chave.
            models.UniqueConstraint(
                Least("requester", "addressee"),
                Greatest("requester", "addressee"),
                name="friendship_unique_pair",
            ),
        ]
        # O Django limita o nome do índice a 30 caracteres (models.E034).
        indexes = [models.Index(fields=["addressee", "status"], name="friendship_addr_stat_idx")]

    def __str__(self) -> str:
        return f"{self.requester_id} -> {self.addressee_id} ({self.status})"
