"""`run_once`: a mesma chave executa a operação uma única vez e devolve a resposta gravada."""

import uuid
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from apps.economy import idempotency, services
from apps.economy.models import IdempotencyRecord

pytestmark = pytest.mark.django_db

ESCOPO = "user:a"
CHAVE = str(uuid.uuid4())
HASH = "a" * 64
OUTRO_HASH = "b" * 64


def _operacao(chamadas: list[int], corpo: dict[str, Any]) -> Any:
    def operar() -> tuple[int, dict[str, Any]]:
        chamadas.append(1)
        return 201, corpo

    return operar


def test_primeira_chamada_executa_e_grava_a_resposta() -> None:
    chamadas: list[int] = []

    saida = idempotency.run_once(
        scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=_operacao(chamadas, {"n": 1})
    )

    assert (saida.status, saida.body, saida.replayed) == (201, {"n": 1}, False)
    assert chamadas == [1]
    registro = IdempotencyRecord.objects.get()
    assert (registro.scope, registro.key, registro.request_hash) == (ESCOPO, CHAVE, HASH)
    assert (registro.response_status, registro.response_body) == (201, {"n": 1})


def test_repeticao_devolve_a_resposta_gravada_sem_executar() -> None:
    chamadas: list[int] = []
    idempotency.run_once(
        scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=_operacao(chamadas, {"n": 1})
    )

    repetida = idempotency.run_once(
        scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=_operacao(chamadas, {"n": 2})
    )

    assert (repetida.status, repetida.body, repetida.replayed) == (201, {"n": 1}, True)
    assert chamadas == [1]  # a segunda operação nem rodou
    assert IdempotencyRecord.objects.count() == 1


def test_mesma_chave_com_pedido_diferente_e_recusada_e_nao_executa() -> None:
    chamadas: list[int] = []
    idempotency.run_once(
        scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=_operacao(chamadas, {"n": 1})
    )

    with pytest.raises(idempotency.IdempotencyKeyReused):
        idempotency.run_once(
            scope=ESCOPO,
            key=CHAVE,
            request_hash=OUTRO_HASH,
            operation=_operacao(chamadas, {"n": 2}),
        )

    assert chamadas == [1]
    registro = IdempotencyRecord.objects.get()
    assert (registro.request_hash, registro.response_body) == (HASH, {"n": 1})


def test_a_mesma_chave_em_escopos_diferentes_executa_nos_dois() -> None:
    chamadas: list[int] = []

    for escopo in ("user:a", "user:b"):
        idempotency.run_once(
            scope=escopo, key=CHAVE, request_hash=HASH, operation=_operacao(chamadas, {"n": 1})
        )

    assert chamadas == [1, 1]
    assert IdempotencyRecord.objects.count() == 2


def test_chaves_diferentes_no_mesmo_escopo_executam_cada_uma() -> None:
    chamadas: list[int] = []

    for chave in (str(uuid.uuid4()), str(uuid.uuid4())):
        idempotency.run_once(
            scope=ESCOPO, key=chave, request_hash=HASH, operation=_operacao(chamadas, {"n": 1})
        )

    assert chamadas == [1, 1]


def test_operacao_que_falha_nao_queima_a_chave() -> None:
    def falha() -> tuple[int, dict[str, Any]]:
        raise services.InsufficientFunds

    with pytest.raises(services.InsufficientFunds):
        idempotency.run_once(scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=falha)

    assert IdempotencyRecord.objects.count() == 0  # o registro desfez junto com a operação
    chamadas: list[int] = []
    saida = idempotency.run_once(
        scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=_operacao(chamadas, {"n": 1})
    )
    assert (saida.replayed, chamadas) == (False, [1])


def test_efeito_da_operacao_desfaz_junto_se_ela_falha_depois_de_gravar() -> None:
    """O registro e a operação são uma transação só: falhar depois desfaz os dois."""
    gravados: list[int] = []

    def grava_e_falha() -> tuple[int, dict[str, Any]]:
        IdempotencyRecord.objects.create(scope="efeito", key=CHAVE, request_hash=HASH)
        gravados.append(1)
        raise RuntimeError("falha depois de gravar")

    with pytest.raises(RuntimeError):
        idempotency.run_once(scope=ESCOPO, key=CHAVE, request_hash=HASH, operation=grava_e_falha)

    assert gravados == [1]
    assert IdempotencyRecord.objects.count() == 0


def test_banco_recusa_dois_registros_com_o_mesmo_escopo_e_chave() -> None:
    IdempotencyRecord.objects.create(scope=ESCOPO, key=CHAVE, request_hash=HASH)

    with pytest.raises(IntegrityError), transaction.atomic():
        IdempotencyRecord.objects.create(scope=ESCOPO, key=CHAVE, request_hash=OUTRO_HASH)
