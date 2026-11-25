"""Idempotência (ESBOÇO INGÊNUO do commit só de testes): executa sempre e não grava nada."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class IdempotencyKeyReused(Exception):
    code = "idempotency_key_reused"
    message = "Esta chave de idempotência já foi usada com outro pedido."


@dataclass(frozen=True)
class Outcome:
    status: int
    body: dict[str, Any]
    replayed: bool


def run_once(
    *,
    scope: str,
    key: str,
    request_hash: str,
    operation: Callable[[], tuple[int, dict[str, Any]]],
) -> Outcome:
    status, body = operation()
    return Outcome(status, body, False)
