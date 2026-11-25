"""Regras puras da troca de itens: sem Django e sem I/O, testáveis sem banco.

Uma oferta é um pedido de troca: o proponente entrega itens seus e recebe itens do destinatário.
Só itens, sem dinheiro. Cada lado tem pelo menos um item (sem "presente puro"), porque uma troca
de um lado só serviria para juntar itens numa conta só (risco J4).
"""

import uuid
from collections.abc import Sequence

PENDING = "pending"
ACCEPTED = "accepted"
DECLINED = "declined"
CANCELLED = "cancelled"

ACCEPT = "accept"
DECLINE = "decline"
CANCEL = "cancel"

# Problemas de forma da oferta e de estado de cada item (o serviço traduz em erros com `code`).
SELF_TRADE = "self_trade"
EMPTY_SIDE = "empty_side"
DUPLICATE_ITEM = "duplicate_item"
NOT_OWNER = "not_owner"
CONSUMED = "consumed"

# O estado terminal que cada ação produz.
_STATUS_AFTER = {ACCEPT: ACCEPTED, DECLINE: DECLINED, CANCEL: CANCELLED}


def offer_shape_problem(
    proposer_id: uuid.UUID,
    recipient_id: uuid.UUID,
    offered: Sequence[uuid.UUID],
    requested: Sequence[uuid.UUID],
) -> str | None:
    """O primeiro problema que a oferta tem só pela forma, ou `None`.

    A ordem é parte do contrato: quem troca, depois o tamanho de cada lado, depois repetição.
    Um item repetido vale tanto dentro de um lado quanto entre os dois lados.
    """
    if proposer_id == recipient_id:
        return SELF_TRADE
    if not offered or not requested:
        return EMPTY_SIDE
    todos = [*offered, *requested]
    if len(set(todos)) != len(todos):
        return DUPLICATE_ITEM
    return None


def item_problem(
    *, expected_owner_id: uuid.UUID, actual_owner_id: uuid.UUID | None, consumed: bool
) -> str | None:
    """O item está com o dono declarado e em jogo? `actual_owner_id=None` é "não existe".

    O dono errado vence o consumido: um item alheio nunca revela se saiu do jogo.
    """
    if actual_owner_id != expected_owner_id:
        return NOT_OWNER
    if consumed:
        return CONSUMED
    return None


def can_resolve(status: str) -> bool:
    """Só a oferta pendente muda de estado; aceita, recusada e cancelada são terminais."""
    return status == PENDING


def may_act(
    action: str, *, actor_id: uuid.UUID, proposer_id: uuid.UUID, recipient_id: uuid.UUID
) -> bool:
    """Aceitar e recusar são do destinatário; cancelar é do proponente. Nega por omissão."""
    if action in (ACCEPT, DECLINE):
        return actor_id == recipient_id
    if action == CANCEL:
        return actor_id == proposer_id
    return False


def status_after(action: str) -> str:
    """O estado terminal que a ação produz."""
    return _STATUS_AFTER[action]
