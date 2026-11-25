"""Idempotência na mesma transação da operação (ADR 0014).

`run_once` insere o registro `(scope, key)` e executa a operação NA MESMA transação:
- chave nova: o registro nasce, a operação roda, a resposta é gravada no registro e tudo
  confirma junto; se a operação falhar, tudo desfaz (a chave não fica "queimada");
- chave já usada com o mesmo pedido: devolve a resposta gravada, sem executar;
- chave já usada com outro pedido: `IdempotencyKeyReused`;
- pedido simultâneo com a mesma chave: o PostgreSQL faz o `INSERT` duplicado ESPERAR a primeira
  transação terminar e só então falhar por unicidade; daí vem a resposta gravada. Por isso não
  existe estado "em andamento" (nem `409 Retry-After`).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from .models import IdempotencyRecord


class IdempotencyKeyReused(Exception):
    """A mesma chave, no mesmo escopo, já foi usada com um pedido diferente."""

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
    """Executa `operation` uma única vez por `(scope, key)` e devolve a resposta (status, corpo).

    `operation` devolve `(status, corpo)`, com o corpo já serializável em JSON.
    """
    with transaction.atomic():
        try:
            with transaction.atomic():  # savepoint: a falha de unicidade não aborta a transação
                registro = IdempotencyRecord.objects.create(
                    scope=scope, key=key, request_hash=request_hash
                )
        except IntegrityError:
            existente = IdempotencyRecord.objects.get(scope=scope, key=key)
            if existente.request_hash[:0] != request_hash[:0]:
                raise IdempotencyKeyReused from None
            if existente.response_status is None or existente.response_body is None:
                raise RuntimeError("registro de idempotência sem resposta") from None
            return Outcome(existente.response_status, existente.response_body, True)

        status, body = operation()
        registro.response_status = status
        registro.response_body = body
        registro.save(update_fields=["response_status", "response_body"])
    return Outcome(status, body, False)
