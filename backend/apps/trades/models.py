import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class TradeStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACCEPTED = "accepted", "Aceita"
    DECLINED = "declined", "Recusada"
    CANCELLED = "cancelled", "Cancelada"


class TradeSide(models.TextChoices):
    OFFERED = "offered", "Oferecido"
    REQUESTED = "requested", "Pedido"


_PENDENTE_SEM_FIM = Q(status="pending", resolved_at__isnull=True)
_RESOLVIDA_COM_FIM = ~Q(status="pending") & Q(resolved_at__isnull=False)


class TradeOffer(models.Model):
    """Um pedido de troca de itens entre dois amigos: `proposer` entrega, `recipient` decide.

    Só `pending` muda de estado (`accepted`, `declined` e `cancelled` são terminais), e
    `resolved_at` é preenchido exatamente quando a oferta deixa de ser pendente. Quem escreve o
    estado é `trades.services`; o dono dos itens, só `inventory.services.change_owner`.
    """

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

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(proposer=F("recipient")), name="tradeoffer_no_self"
            ),
            models.CheckConstraint(
                condition=Q(status__in=TradeStatus.values), name="tradeoffer_status_valid"
            ),
            # `resolved_at` nulo se, e só se, a oferta está pendente.
            models.CheckConstraint(
                condition=_PENDENTE_SEM_FIM | _RESOLVIDA_COM_FIM,
                name="tradeoffer_resolved_matches_status",
            ),
        ]
        # O Django limita o nome do índice a 30 caracteres (models.E034).
        indexes = [
            models.Index(fields=["recipient", "status"], name="tradeoffer_recip_status_idx"),
            models.Index(fields=["proposer", "status"], name="tradeoffer_prop_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.proposer_id} -> {self.recipient_id} ({self.status})"


class TradeOfferItem(models.Model):
    """Um item dentro de uma oferta, de um dos dois lados.

    `active` repete "a oferta está pendente" no item, de propósito: um índice único parcial não
    enxerga outra tabela, e é ele quem garante, no banco, que uma instância esteja em no máximo
    UMA oferta pendente. O serviço liga `active` ao criar e o desliga na mesma transação que
    resolve a oferta (aceitar, recusar ou cancelar).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(TradeOffer, on_delete=models.PROTECT, related_name="items")
    instance = models.ForeignKey(
        "inventory.SkinInstance", on_delete=models.PROTECT, related_name="trade_items"
    )
    side = models.CharField(max_length=10, choices=TradeSide.choices)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offer", "instance"], name="tradeitem_unique_offer_instance"
            ),
            models.UniqueConstraint(
                fields=["instance"],
                condition=Q(active=True),
                name="tradeitem_one_active_per_instance",
            ),
            models.CheckConstraint(
                condition=Q(side__in=TradeSide.values), name="tradeitem_side_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.instance_id} ({self.side}) na oferta {self.offer_id}"
