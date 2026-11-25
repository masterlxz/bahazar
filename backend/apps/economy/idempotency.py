"""Idempotência na mesma transação da operação (ADR 0014).

`run_once` insere o registro `(scope, key)` e executa a operação NA MESMA transação:
- chave nova: o registro nasce, a operação roda, a resposta é gravada no registro e tudo
  confirma junto; se a operação falhar, tudo desfaz (a chave não fica "queimada");
- chave já usada com o mesmo pedido: devolve a resposta gravada, sem executar;
- chave já usada com outro pedido: `IdempotencyKeyReused`;
- pedido simultâneo com a mesma chave: o PostgreSQL faz o `INSERT` duplicado ESPERAR a primeira
  transação terminar e só então falhar por unicidade; daí vem a resposta gravada. Por isso não
  existe estado "em andamento" (nem `409 Retry-After`);
- registro apagado pela expiração (`expire_idempotency`) entre o `INSERT` que falhou e o `SELECT`:
  a chave ficou livre, então o `INSERT` é refeito (é pedido novo, mesmo com outro hash), até
  `MAX_ATTEMPTS` vezes; esgotado o limite levanta `RuntimeError` (o pedido não executou).

Contrato: assume o isolamento READ COMMITTED (o padrão do Django e deste projeto): o `SELECT`
depois da falha de unicidade precisa enxergar a linha confirmada pela outra transação. Não chamar
de dentro de uma transação REPEATABLE READ ou SERIALIZABLE sem rever isto.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from .models import IdempotencyRecord

MAX_ATTEMPTS = 3  # INSERTs de `run_once` quando o registro some entre o INSERT e o SELECT


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
        for _ in range(MAX_ATTEMPTS):
            try:
                with transaction.atomic():  # savepoint: a falha de unicidade não aborta a transação
                    registro = IdempotencyRecord.objects.create(
                        scope=scope, key=key, request_hash=request_hash
                    )
            except IntegrityError:
                try:
                    existente = IdempotencyRecord.objects.get(scope=scope, key=key)
                except IdempotencyRecord.DoesNotExist:
                    continue  # expirou entre o INSERT e o SELECT: a chave está livre, tenta de novo
                if existente.request_hash != request_hash:
                    raise IdempotencyKeyReused from None
                if existente.response_status is None or existente.response_body is None:
                    raise RuntimeError("registro de idempotência sem resposta") from None
                return Outcome(existente.response_status, existente.response_body, True)
            break
        else:
            raise RuntimeError(
                f"registro de idempotência apagado a cada uma das {MAX_ATTEMPTS} tentativas"
            )

        status, body = operation()
        registro.response_status = status
        registro.response_body = body
        registro.save(update_fields=["response_status", "response_body"])
    return Outcome(status, body, False)
