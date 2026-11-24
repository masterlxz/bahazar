import uuid

from django.db import models
from django.db.models import F, Q


class Skin(models.Model):
    """Uma skin do catálogo. Global: não pertence a usuário nem a grupo.

    `reference_price` é o preço de referência em centavos de USD (ADR 0011), dado nosso
    atualizado por import. `image_*` ficam em branco até a decisão D1 (PR 3.3).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=64, unique=True)
    weapon = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    collection = models.CharField(max_length=200, blank=True)
    rarity = models.CharField(max_length=64)
    min_float = models.DecimalField(max_digits=10, decimal_places=9)
    max_float = models.DecimalField(max_digits=10, decimal_places=9)
    reference_price = models.BigIntegerField()
    image_url = models.CharField(max_length=500, blank=True, default="")
    image_source = models.CharField(max_length=20, default="none")
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(min_float__gte=0, min_float__lt=F("max_float"), max_float__lte=1),
                name="skin_float_range",
            ),
            models.CheckConstraint(
                condition=Q(reference_price__gt=0), name="skin_reference_price_positive"
            ),
        ]

    def __str__(self) -> str:
        return self.name
