import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class AcquiredVia(models.TextChoices):
    ADMIN_GRANT = "admin_grant", "Concedida pelo administrador"


class SkinInstance(models.Model):
    """Um item de um jogador: uma cópia de uma skin do catálogo, com o seu float.

    Cada instância tem UM dono. O float fica sempre dentro da faixa da skin (trigger no banco,
    migração 0002). O desgaste é derivado do float (`rules.wear_for`), não é coluna.
    `consumed_at` marca um item que saiu do jogo; ele não é apagado (auditoria).
    Só `inventory.services` cria instâncias (GUIDELINES 2).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skin = models.ForeignKey("catalog.Skin", on_delete=models.PROTECT, related_name="instances")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="skin_instances"
    )
    float_value = models.DecimalField(max_digits=10, decimal_places=9)
    acquired_via = models.CharField(max_length=20, choices=AcquiredVia.choices)
    acquired_at = models.DateTimeField(auto_now_add=True)
    acquired_ref_id = models.UUIDField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(float_value__gte=0, float_value__lte=1),
                name="skininstance_float_unit_range",
            ),
            models.CheckConstraint(
                condition=Q(acquired_via__in=AcquiredVia.values),
                name="skininstance_acquired_via_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner"],
                condition=Q(consumed_at__isnull=True),
                name="skininstance_owner_active_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.skin_id} de {self.owner_id} ({self.float_value})"
