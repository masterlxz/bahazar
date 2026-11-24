"""Concorrência do teto de salas por dono contra Postgres real (caracterização).

`services.create_room` trava a linha do usuário (`User.objects.select_for_update()`) antes de
contar as salas ativas dele (`rules.can_create_room`). Sem essa trava, duas criações simultâneas
de quem já tem `MAX_ROOMS_AS_OWNER - 1` salas leriam a mesma contagem, passariam as duas e o dono
ficaria com mais salas que o teto.

Estes testes descrevem o comportamento que já existe: passam na `main`. A mudança que os faria
falhar é tirar a linha `User.objects.select_for_update().get(pk=user.pk)` de `create_room`
(`apps/rooms/services.py`): aí mais de uma das N criações do primeiro caso poderia ter sucesso e
a contagem final passar do teto (depende do agendamento), e o teste da trava segurada
(`test_criar_sala_espera_a_trava_da_linha_do_dono_ser_solta`) falharia sempre, porque a criação
terminaria sem esperar. Essa prova (mutação) NÃO foi rodada por quem escreveu os testes.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection, transaction

from apps.accounts.models import User
from apps.rooms import rules, services
from apps.rooms.models import Room

from .conftest import criar_usuario

N = 6
ESPERA_MAXIMA_S = 30
ESPERA_BLOQUEIO_S = 1


def _salas_ativas(dono: Any) -> int:
    return Room.objects.filter(owner=dono, archived_at__isnull=True).count()


def _largar(donos: list[Any]) -> list[str]:
    """Cada item de `donos` cria uma sala no mesmo instante; devolve "ok" ou o `code` do erro.

    Cada thread abre a conexão antes da barreira, para o custo de conectar não cair depois da
    largada e escalonar as transações por acaso. A barreira prende as threads até a última chegar
    e as solta juntas; se alguma não chegar em `ESPERA_MAXIMA_S`, ela levanta `BrokenBarrierError`
    e o teste falha (não há asserção própria sobre isso). Isso garante a largada conjunta, não
    que as consultas se sobreponham no banco.
    """
    largada = threading.Barrier(len(donos), timeout=ESPERA_MAXIMA_S)

    def tentar(dono: Any) -> str:
        try:
            connection.ensure_connection()
            largada.wait()
            services.create_room(dono, "Nova")
            return "ok"
        except services.RoomError as erro:
            return erro.code
        finally:
            connection.close()

    with ThreadPoolExecutor(len(donos)) as pool:
        futuros = [pool.submit(tentar, d) for d in donos]
        return [f.result(timeout=ESPERA_MAXIMA_S) for f in futuros]


@pytest.mark.django_db(transaction=True)
def test_dono_com_uma_vaga_cria_so_uma_sala_entre_as_criacoes_simultaneas() -> None:
    dono = criar_usuario("dono_01")
    for i in range(rules.MAX_ROOMS_AS_OWNER - 1):
        services.create_room(dono, f"Sala {i}")
    assert _salas_ativas(dono) == rules.MAX_ROOMS_AS_OWNER - 1  # premissa: falta uma vaga

    resultados = _largar([dono] * N)

    assert sorted(resultados) == ["ok"] + ["room_limit_reached"] * (N - 1)
    assert _salas_ativas(dono) == rules.MAX_ROOMS_AS_OWNER


@pytest.mark.django_db(transaction=True)
def test_dono_sem_salas_nunca_passa_do_teto_com_criacoes_simultaneas() -> None:
    """N > teto: cabem exatamente `MAX_ROOMS_AS_OWNER`, as demais recebem `room_limit_reached`."""
    dono = criar_usuario("dono_01")
    assert N > rules.MAX_ROOMS_AS_OWNER  # premissa: há mais tentativas que vagas
    assert _salas_ativas(dono) == 0

    resultados = _largar([dono] * N)

    teto = rules.MAX_ROOMS_AS_OWNER
    assert sorted(resultados) == ["ok"] * teto + ["room_limit_reached"] * (N - teto)
    assert _salas_ativas(dono) == rules.MAX_ROOMS_AS_OWNER


@pytest.mark.django_db(transaction=True)
def test_donos_diferentes_criam_cada_um_a_sua_sala() -> None:
    """A trava é por usuário: a corrida de um dono não faz outro receber `room_limit_reached`."""
    donos = [criar_usuario(f"dono_{i}") for i in range(N)]
    for dono in donos:
        for i in range(rules.MAX_ROOMS_AS_OWNER - 1):
            services.create_room(dono, f"Sala {i}")
    assert [_salas_ativas(d) for d in donos] == [rules.MAX_ROOMS_AS_OWNER - 1] * N

    resultados = _largar(donos)

    assert resultados == ["ok"] * N
    assert [_salas_ativas(d) for d in donos] == [rules.MAX_ROOMS_AS_OWNER] * N


@pytest.mark.django_db(transaction=True)
def test_criar_sala_espera_a_trava_da_linha_do_dono_ser_solta() -> None:
    """Prova da trava sem depender de corrida: a thread principal segura a linha do dono e a
    criação, em outra thread, tem de ficar parada até a trava cair.

    Sem o `select_for_update` em `create_room`, a thread terminaria na hora e `done()` seria
    verdadeiro durante a espera.

    Por que `no_key=True` (`FOR NO KEY UPDATE`): a FK `Room.owner` faz o Postgres tomar
    `FOR KEY SHARE` na linha do usuário, que conflita com `FOR UPDATE` mas não com `NO KEY
    UPDATE`. Com `FOR UPDATE` aqui a criação pararia por causa da FK, mesmo sem a trava de
    `create_room`; com `NO KEY UPDATE` só o `FOR UPDATE` de `create_room` bloqueia.
    """
    dono = criar_usuario("dono_01")
    for i in range(rules.MAX_ROOMS_AS_OWNER - 1):
        services.create_room(dono, f"Sala {i}")
    assert _salas_ativas(dono) == rules.MAX_ROOMS_AS_OWNER - 1  # premissa: falta uma vaga

    def criar() -> Room:
        try:
            return services.create_room(dono, "X")
        finally:
            connection.close()

    with ThreadPoolExecutor(1) as pool:
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=dono.pk)
            futuro = pool.submit(criar)
            time.sleep(ESPERA_BLOQUEIO_S)
            assert not futuro.done()  # a criação está parada na trava do dono
        # ao sair do atomic o commit solta a trava

        sala = futuro.result(timeout=ESPERA_MAXIMA_S)

    assert sala.owner_id == dono.pk
    assert _salas_ativas(dono) == rules.MAX_ROOMS_AS_OWNER
