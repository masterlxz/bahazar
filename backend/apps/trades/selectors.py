"""Leitura das trocas, sempre escopada a quem faz parte da oferta (GUIDELINES 6)."""

import uuid
from collections.abc import Iterable

from django.db.models import Prefetch, Q, QuerySet, prefetch_related_objects

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


def offers_of(user: User) -> QuerySet[TradeOffer]:
    """As ofertas de que `user` faz parte (enviadas e recebidas), das mais novas às mais antigas.

    O `id` é o desempate: sem ele a paginação repete ou pula ofertas criadas no mesmo instante.
    """
    ofertas = TradeOffer.objects.filter(Q(proposer=user) | Q(recipient=user))
    return ofertas.select_related("proposer", "recipient").order_by("-created_at", "id")


def load_items(offers: Iterable[TradeOffer]) -> None:
    """Carrega os itens das ofertas (com a instância e a skin) em UMA consulta extra.

    Sem isto o serializer consultaria itens, instâncias e skins uma vez por oferta. Os itens
    saem em ordem fixa (lado, depois id da instância), para a resposta não variar.
    """
    itens = TradeOfferItem.objects.select_related("instance__skin").order_by("side", "instance_id")
    prefetch_related_objects(list(offers), Prefetch("items", queryset=itens))


def pending_count(proposer: User) -> int:
    """Quantas ofertas pendentes `proposer` tem como proponente.

    Só `pending` conta: recusar, cancelar e ACEITAR a oferta liberam a vaga.
    """
    return TradeOffer.objects.filter(proposer=proposer, status=TradeStatus.PENDING).count()


def busy_instance_ids(instance_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Das instâncias dadas, as que já estão numa oferta pendente (de qualquer dono)."""
    ocupadas = TradeOfferItem.objects.filter(instance_id__in=list(instance_ids), active=True)
    return set(ocupadas.values_list("instance_id", flat=True))
