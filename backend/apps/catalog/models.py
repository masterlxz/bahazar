import uuid

from django.db import models
from django.db.models import F, Q


class Skin(models.Model):
    """Uma skin do catálogo. Global: não pertence a usuário nem a grupo.

    `reference_price` é o preço de referência em centavos de USD (ADR 0011), dado nosso
    atualizado por import. `image_*` ficam em branco até a decisão D1 (PR 3.3).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # type: ignore
    external_id = models.CharField(max_length=64, unique=True)  # type: ignore
    weapon = models.CharField(max_length=64)  # type: ignore
    name = models.CharField(max_length=200)  # type: ignore
    collection = models.CharField(max_length=200, blank=True)  # type: ignore
    rarity = models.CharField(max_length=64)  # type: ignore
    min_float = models.DecimalField(max_digits=10, decimal_places=9)  # type: ignore
    max_float = models.DecimalField(max_digits=10, decimal_places=9)  # type: ignore
    reference_price = models.BigIntegerField()  # type: ignore
    image_url = models.CharField(max_length=500, blank=True, default="")  # type: ignore
    image_source = models.CharField(max_length=20, default="none")  # type: ignore
    active = models.BooleanField(default=True)  # type: ignore

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
