"""Idempotência e transferência sob concorrência, contra PostgreSQL real (PR 4.1).

Dinheiro: pressa, clique duplo e transferências cruzadas não duplicam nem perdem valor, e o
ledger continua fechando (`audit.check_ledger`).
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from apps.economy import audit, idempotency, services
from apps.economy.models import IdempotencyRecord, Wallet, WalletTransaction

from .conftest import criar_usuario

N = 6
ESPERA_MAXIMA_S = 30
SALDO_INICIAL = 2_500  # US$ 25,00 (ADR 0013)

pytestmark = pytest.mark.django_db(transaction=True)


def _largar(tarefas: list[Any]) -> list[Any]:
    """Roda cada tarefa numa thread, todas soltas juntas por uma barreira; devolve os resultados.

    Uma exceção da tarefa vira o resultado (`services.EconomyError`) para o teste contar; outra
    exceção propaga e falha o teste. A conexão abre antes da barreira, para só a transação disputar.
    """
    largada = threading.Barrier(len(tarefas), timeout=ESPERA_MAXIMA_S)

    def rodar(tarefa: Any) -> Any:
        try:
            connection.ensure_connection()
            largada.wait()
            return tarefa()
        except (services.EconomyError, idempotency.IdempotencyKeyReused) as erro:
            return erro
        finally:
            connection.close()

    with ThreadPoolExecutor(len(tarefas)) as pool:
        futuros = [pool.submit(rodar, t) for t in tarefas]
        return [f.result(timeout=ESPERA_MAXIMA_S) for f in futuros]


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def _grupos_de_transferencia() -> int:
    return WalletTransaction.objects.filter(kind="transfer").values("group_id").distinct().count()


def test_a_mesma_chave_em_varias_threads_transfere_uma_unica_vez() -> None:
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    chave = str(uuid.uuid4())

    resultados = _largar(
        [lambda: services.transfer(ana, bruno, 1_000, idempotency_key=chave) for _ in range(N)]
    )

    assert all(isinstance(r, services.TransferResult) for r in resultados)
    assert sorted(r.replayed for r in resultados) == [False] + [True] * (N - 1)
    assert len({r.ledger_group_id for r in resultados}) == 1
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - 1_000, SALDO_INICIAL + 1_000)
    assert _grupos_de_transferencia() == 1
    assert IdempotencyRecord.objects.count() == 1
    assert audit.check_ledger() == []


def test_a_mesma_chave_com_valores_diferentes_em_paralelo_so_um_pedido_vence() -> None:
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    chave = str(uuid.uuid4())
    valores = [100, 200] * (N // 2)

    resultados = _largar(
        [lambda v=v: services.transfer(ana, bruno, v, idempotency_key=chave) for v in valores]
    )

    feitos = [r for r in resultados if isinstance(r, services.TransferResult)]
    vencedores = [r for r in feitos if not r.replayed]
    repetidos = [r for r in feitos if r.replayed]
    recusados = [r for r in resultados if isinstance(r, idempotency.IdempotencyKeyReused)]
    assert len(vencedores) == 1
    assert len(repetidos) == N // 2 - 1  # os que pediram o mesmo valor do vencedor
    assert len(recusados) == N // 2  # os que pediram o outro valor: chave reusada
    assert _saldo(ana) == SALDO_INICIAL - vencedores[0].amount
    assert _grupos_de_transferencia() == 1
    assert IdempotencyRecord.objects.count() == 1
    assert audit.check_ledger() == []


def test_a_mesma_chave_acima_do_saldo_em_paralelo_recusa_todas_e_nao_queima_a_chave() -> None:
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    chave = str(uuid.uuid4())

    resultados = _largar(
        [
            lambda: services.transfer(ana, bruno, SALDO_INICIAL + 1, idempotency_key=chave)
            for _ in range(N)
        ]
    )

    assert all(isinstance(r, services.InsufficientFunds) for r in resultados)
    assert IdempotencyRecord.objects.count() == 0  # quem esperava não ficou preso a um registro
    assert _grupos_de_transferencia() == 0
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL, SALDO_INICIAL)
    services.transfer(ana, bruno, 100, idempotency_key=chave)  # a chave segue valendo
    assert _saldo(ana) == SALDO_INICIAL - 100


def test_chaves_diferentes_em_paralelo_transferem_cada_uma() -> None:
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")

    resultados = _largar(
        [
            lambda: services.transfer(ana, bruno, 100, idempotency_key=str(uuid.uuid4()))
            for _ in range(N)
        ]
    )

    assert all(isinstance(r, services.TransferResult) and not r.replayed for r in resultados)
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - N * 100, SALDO_INICIAL + N * 100)
    assert _grupos_de_transferencia() == N
    assert audit.check_ledger() == []


def test_gasto_simultaneo_acima_do_saldo_aprova_so_o_que_cabe() -> None:
    """Saldo de 2.500 e N pedidos de 1.000: cabem exatamente dois; os outros recebem recusa."""
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")

    resultados = _largar(
        [
            lambda: services.transfer(ana, bruno, 1_000, idempotency_key=str(uuid.uuid4()))
            for _ in range(N)
        ]
    )

    aprovados = [r for r in resultados if isinstance(r, services.TransferResult)]
    recusados = [r for r in resultados if isinstance(r, services.InsufficientFunds)]
    assert (len(aprovados), len(recusados)) == (2, N - 2)
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - 2_000, SALDO_INICIAL + 2_000)
    assert _grupos_de_transferencia() == 2
    assert IdempotencyRecord.objects.count() == 2  # as recusadas não deixam registro
    assert audit.check_ledger() == []


def test_transferencias_cruzadas_nao_travam_e_o_ledger_fecha() -> None:
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")

    def ida() -> Any:
        return services.transfer(ana, bruno, 100, idempotency_key=str(uuid.uuid4()))

    def volta() -> Any:
        return services.transfer(bruno, ana, 100, idempotency_key=str(uuid.uuid4()))

    resultados = _largar([ida, volta] * (N // 2))

    assert all(isinstance(r, services.TransferResult) for r in resultados)  # nenhum deadlock
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL, SALDO_INICIAL)
    assert _grupos_de_transferencia() == N
    assert audit.check_ledger() == []


def test_repeticoes_com_a_expiracao_apagando_registros_nao_deixam_escapar_erro_cru() -> None:
    """Corrida expiração × retry com threads reais (A2 g).

    Uma thread apaga todos os registros em laço (o que `expire_idempotency` faz, só que sem
    parar); N threads repetem a MESMA chave. Cada chamada tem de acabar em `Outcome` ou em
    `IdempotencyExhausted`; `IntegrityError` ou `DoesNotExist` crus nunca podem escapar, e todo
    corpo repetido (`replayed`) é um corpo que a operação de fato produziu. NÃO fixa qual desfecho
    aparece (depende de o `DELETE` cair entre o `INSERT` e o `SELECT`) nem que a operação rode uma
    vez só: depois da expiração a guarda contra execução dupla é do CHAMADOR (docstring de
    `idempotency`).
    """
    repeticoes = 15
    produzidos: list[dict[str, Any]] = []

    def operacao() -> tuple[int, dict[str, Any]]:
        corpo = {"execucao": str(uuid.uuid4())}
        produzidos.append(corpo)
        return 201, corpo

    parar = threading.Event()

    def apagar() -> None:
        try:
            while not parar.is_set():
                IdempotencyRecord.objects.all().delete()
        finally:
            connection.close()

    def repetir() -> list[Any]:
        try:
            saidas: list[Any] = []
            for _ in range(repeticoes):
                try:
                    saidas.append(
                        idempotency.run_once(
                            scope="user:corrida",
                            key="chave-unica",
                            request_hash="h",
                            operation=operacao,
                        )
                    )
                except idempotency.IdempotencyExhausted as erro:
                    saidas.append(erro)
            return saidas
        finally:
            connection.close()

    with ThreadPoolExecutor(N + 1) as pool:
        apagador = pool.submit(apagar)
        try:
            por_thread = [
                f.result(timeout=ESPERA_MAXIMA_S) for f in [pool.submit(repetir) for _ in range(N)]
            ]
        finally:
            parar.set()
        apagador.result(timeout=ESPERA_MAXIMA_S)

    saidas = [s for lista in por_thread for s in lista]
    assert len(saidas) == N * repeticoes
    assert produzidos, "nenhuma chamada executou a operação"
    for saida in saidas:
        assert isinstance(saida, idempotency.Outcome | idempotency.IdempotencyExhausted)
        if isinstance(saida, idempotency.Outcome) and saida.replayed:
            assert saida.body in produzidos
