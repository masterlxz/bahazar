import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from . import rules


class ListingStatus(models.TextChoices):
    ACTIVE = rules.ACTIVE, "Ativo"
    SOLD = rules.SOLD, "Vendido"
    CANCELLED = rules.CANCELLED, "Cancelado"


class MarketListing(models.Model):
    """Um anúncio global de um item, em centavos. Só o vendedor pode cancelá-lo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="market_listings",
    )
    instance = models.ForeignKey(
        "inventory.SkinInstance",
        on_delete=models.PROTECT,
        related_name="market_listings",
    )
    price = models.BigIntegerField()
    status = models.CharField(
        max_length=10,
        choices=ListingStatus.choices,
        default=ListingStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gt=0),
                name="marketlisting_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(status__in=ListingStatus.values),
                name="marketlisting_status_valid",
            ),
            models.UniqueConstraint(
                fields=["instance"],
                condition=Q(status=ListingStatus.ACTIVE),
                name="marketlist_one_active_instance",
            ),
        ]
        indexes = [
            models.Index(
                fields=["seller"],
                name="marketlisting_seller_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="marketlist_status_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.instance_id} por {self.seller_id} ({self.price})"
