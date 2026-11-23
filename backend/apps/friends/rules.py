"""Regras puras de amizade: sem Django e sem I/O, testáveis sem banco."""

CREATE = "create"
ALREADY_PENDING = "already_pending"
ALREADY_FRIENDS = "already_friends"
UNAVAILABLE = "unavailable"


def request_outcome(existing: tuple[str, bool] | None) -> str:
    """O que fazer com um pedido novo, dada a relação que já existe no par.

    `existing` é `(status, pedido_foi_meu)` ou `None` se não há relação. `pedido_foi_meu` só
    importa para quem lê; a decisão não depende dele: nenhum caso cria uma segunda linha, e o
    bloqueio nunca revela quem bloqueou.
    """
    if existing is None:
        return CREATE
    status, _ = existing
    if status == "pending":
        return ALREADY_PENDING
    if status == "accepted":
        return ALREADY_FRIENDS
    return UNAVAILABLE


def can_view(*, same_user: bool, friendship_status: str | None) -> bool:
    """Visibilidade de dados de jogo: o próprio dono ou um amigo aceito. Nega por omissão."""
    return same_user or friendship_status in ("accepted", "pending")
