import uuid

from django.conf import settings
from django.db import models


class TradeStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACCEPTED = "accepted", "Aceita"
    DECLINED = "declined", "Recusada"
    CANCELLED = "cancelled", "Cancelada"


class TradeSide(models.TextChoices):
    OFFERED = "offered", "Oferecido"
    REQUESTED = "requested", "Pedido"


class TradeOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trade_offers_sent"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trade_offers_received"
    )
    status = models.CharField(
        max_length=10, choices=TradeStatus.choices, default=TradeStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class TradeOfferItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(TradeOffer, on_delete=models.PROTECT, related_name="items")
    instance = models.ForeignKey(
        "inventory.SkinInstance", on_delete=models.PROTECT, related_name="trade_items"
    )
    side = models.CharField(max_length=10, choices=TradeSide.choices)
    active = models.BooleanField(default=True)
