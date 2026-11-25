"""Leitura das trocas, sempre escopada a quem faz parte da oferta (GUIDELINES 6)."""

import uuid
from collections.abc import Iterable

from django.db.models import Q

from apps.accounts.models import User

from .models import TradeOffer, TradeOfferItem, TradeStatus


def offer_for_party(user: User, offer_id: uuid.UUID) -> TradeOffer | None:
    """A oferta, se `user` é o proponente ou o destinatário; senão `None`.

    Quem não faz parte recebe o mesmo `None` de uma oferta que não existe: a view responde 404
    nos dois casos e não revela que a oferta existe.
    """
    return (
        TradeOffer.objects.filter(Q(proposer=user) | Q(recipient=user), pk=offer_id)
        .select_related("proposer", "recipient")
        .first()
    )


def pending_count(proposer: User) -> int:
    """Quantas ofertas pendentes `proposer` tem como proponente.

    Só `pending` conta: recusar, cancelar e ACEITAR a oferta liberam a vaga.
    """
    return TradeOffer.objects.filter(proposer=proposer, status=TradeStatus.PENDING).count()


def busy_instance_ids(instance_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Das instâncias dadas, as que já estão numa oferta pendente (de qualquer dono)."""
    ocupadas = TradeOfferItem.objects.filter(instance_id__in=list(instance_ids), active=True)
    return set(ocupadas.values_list("instance_id", flat=True))
