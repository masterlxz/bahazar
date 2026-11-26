import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from . import rules


class ListingStatus(models.TextChoices):
    ACTIVE = rules.ACTIVE, "Ativo"
    SOLD = rules.SOLD, "Vendido"
    CANCELLED = rules.CANCELLED, "Cancelado"


# `closed_at` é nulo se, e só se, o anúncio está ativo: cada ramo é um estado válido inteiro.
_ATIVO_SEM_FIM = Q(status=ListingStatus.ACTIVE, closed_at__isnull=True)
_FECHADO_COM_FIM = ~Q(status=ListingStatus.ACTIVE) & Q(closed_at__isnull=False)


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
            models.CheckConstraint(
                condition=_ATIVO_SEM_FIM | _FECHADO_COM_FIM,
                name="marketlisting_closed_matches_status",
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


class MarketTransaction(models.Model):
    """Uma venda concluída. Só se escreve, nunca se muda: o banco barra UPDATE e DELETE (trigger).

    Uma por anúncio (`listing` único): é a chave de negócio que impede vender duas vezes, mesmo
    que a idempotência da requisição expire. A ligação com o dinheiro é `ledger_group_id`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(
        MarketListing,
        on_delete=models.PROTECT,
        related_name="sale",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="market_purchases",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="market_sales",
    )
    price = models.BigIntegerField()
    fee = models.BigIntegerField()
    ledger_group_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(buyer=F("seller")),
                name="markettx_buyer_not_seller",
            ),
            # `0 <= taxa < preço` já garante preço positivo e vendedor recebendo pelo menos 1.
            models.CheckConstraint(
                condition=Q(fee__gte=0) & Q(fee__lt=F("price")),
                name="markettx_fee_below_price",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.listing_id}: {self.buyer_id} comprou de {self.seller_id} ({self.price})"
