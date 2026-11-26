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
  a chave ficou livre, então o `INSERT` é refeito (para o `run_once` é pedido novo, mesmo com
  outro hash), até `MAX_ATTEMPTS` vezes; esgotado o limite levanta `RuntimeError`, encadeado ao
  último `IntegrityError` (o pedido não executou).

Depois da expiração a segurança contra execução dupla é do CHAMADOR: "pedido novo" vale só para o
`run_once`, não para quem o chama. Toda `operation` precisa de uma guarda própria e durável de
unicidade além deste registro (no `transfer`, o UNIQUE `wallettx_unique_idempotency_key` do
ledger; ver `test_transferencia_repetida_depois_de_expirar_nao_move_dinheiro_de_novo` em
`tests/economy/test_expire_idempotency.py`). Exceção aceita pelo dono (2026-11-26): o criar
anúncio do `marketplace` não tem essa guarda; só a retenção protege (ADR 0018, adendo da 4.4b).

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


class IdempotencyExhausted(RuntimeError):
    """O `run_once` esgotou as tentativas: o pedido NÃO foi executado e repetir é seguro.

    Herda de `RuntimeError` para não quebrar quem a capturava. `code` e `message` são o que a API
    mostra (503); `str(erro)` é o texto técnico, para o log, e vem encadeado ao último
    `IntegrityError`.
    """

    code = "idempotency_unavailable"
    message = (
        "Não foi possível registrar a chave de idempotência agora. Nada foi feito: "
        "repita o pedido com a mesma chave."
    )


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
    ultimo_erro: IntegrityError | None = None
    with transaction.atomic():
        for _ in range(MAX_ATTEMPTS):
            try:
                with transaction.atomic():  # savepoint: a falha de unicidade não aborta a transação
                    registro = IdempotencyRecord.objects.create(
                        scope=scope, key=key, request_hash=request_hash
                    )
            except IntegrityError as erro:
                ultimo_erro = erro
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
                "idempotência: não achou o registro apagado nem conseguiu inserir em "
                f"{MAX_ATTEMPTS} tentativas"
            ) from ultimo_erro

        status, body = operation()
        registro.response_status = status
        registro.response_body = body
        registro.save(update_fields=["response_status", "response_body"])
    return Outcome(status, body, False)
