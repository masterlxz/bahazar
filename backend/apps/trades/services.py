import uuid
from collections.abc import Sequence

from apps.accounts.models import User

from .models import TradeOffer


class TradeError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "trade_error"
    message = "Operação não permitida."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class SelfTrade(TradeError):
    code = "self_trade"
    message = "Não dá para trocar itens consigo mesmo."


class EmptySide(TradeError):
    code = "empty_side"
    message = "Cada lado da troca precisa de pelo menos um item."


class DuplicateItem(TradeError):
    code = "duplicate_item"
    message = "O mesmo item aparece mais de uma vez na troca."


class NotFriends(TradeError):
    code = "not_friends"
    message = "A troca só é possível entre amigos."


class ItemNotOwned(TradeError):
    code = "item_not_owned"
    message = "Um dos itens não pertence a quem deveria."


class ItemConsumed(TradeError):
    code = "item_consumed"
    message = "Um dos itens já saiu do jogo."


class ItemAlreadyOffered(TradeError):
    code = "item_already_offered"
    message = "Um dos itens já está em outra troca pendente."


class OfferNotFound(TradeError):
    """A oferta não existe ou o chamador não faz parte dela: a view responde 404."""

    code = "offer_not_found"
    message = "Não encontrado."


class NotAllowed(TradeError):
    code = "not_allowed"
    message = "Você não pode fazer isto nesta troca."


class OfferNotPending(TradeError):
    code = "offer_not_pending"
    message = "Esta troca já foi resolvida."


def create_offer(
    proposer: User,
    recipient: User,
    offered_ids: Sequence[uuid.UUID],
    requested_ids: Sequence[uuid.UUID],
) -> TradeOffer:
    raise NotImplementedError


def accept_offer(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    raise NotImplementedError


def decline_offer(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    raise NotImplementedError


def cancel_offer(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    raise NotImplementedError
