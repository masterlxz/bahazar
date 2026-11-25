import uuid
from collections.abc import Iterable

from apps.accounts.models import User

from .models import TradeOffer


def offer_for_party(user: User, offer_id: uuid.UUID) -> TradeOffer | None:
    raise NotImplementedError


def busy_instance_ids(instance_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    raise NotImplementedError
