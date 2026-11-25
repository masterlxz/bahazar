"""Regras puras da troca de itens: sem Django e sem I/O, testáveis sem banco."""

import uuid
from collections.abc import Sequence

PENDING = "pending"
ACCEPTED = "accepted"
DECLINED = "declined"
CANCELLED = "cancelled"

ACCEPT = "accept"
DECLINE = "decline"
CANCEL = "cancel"

SELF_TRADE = "self_trade"
EMPTY_SIDE = "empty_side"
DUPLICATE_ITEM = "duplicate_item"
NOT_OWNER = "not_owner"
CONSUMED = "consumed"


def offer_shape_problem(
    proposer_id: uuid.UUID,
    recipient_id: uuid.UUID,
    offered: Sequence[uuid.UUID],
    requested: Sequence[uuid.UUID],
) -> str | None:
    raise NotImplementedError


def item_problem(
    *, expected_owner_id: uuid.UUID, actual_owner_id: uuid.UUID | None, consumed: bool
) -> str | None:
    raise NotImplementedError


def can_resolve(status: str) -> bool:
    raise NotImplementedError


def may_act(
    action: str, *, actor_id: uuid.UUID, proposer_id: uuid.UUID, recipient_id: uuid.UUID
) -> bool:
    raise NotImplementedError


def status_after(action: str) -> str:
    raise NotImplementedError
