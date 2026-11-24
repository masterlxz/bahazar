"""Concorrência do teto de salas por dono contra Postgres real (caracterização).

`services.create_room` trava a linha do usuário (`User.objects.select_for_update()`) antes de
contar as salas ativas dele (`rules.can_create_room`). Sem essa trava, duas criações simultâneas
de quem já tem `MAX_ROOMS_AS_OWNER - 1` salas leriam a mesma contagem, passariam as duas e o dono
ficaria com mais salas que o teto.

Estes testes descrevem o comportamento que já existe: passam na `main`. A mudança que os faria
falhar é tirar a linha `User.objects.select_for_update().get(pk=user.pk)` de `create_room`
(`apps/rooms/services.py`): aí mais de uma das N criações do primeiro caso teria sucesso e a
contagem final passaria do teto. Essa prova (mutação) NÃO foi rodada por quem escreveu o teste.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from apps.rooms import rules, services
from apps.rooms.models import Room

from .conftest import criar_usuario

N = 6
ESPERA_MAXIMA_S = 30


def _salas_ativas(dono: Any) -> int:
    return Room.objects.filter(owner=dono, archived_at__isnull=True).count()


def _largar(donos: list[Any]) -> list[str]:
    """Cada item de `donos` cria uma sala no mesmo instante; devolve "ok" ou o `code` do erro.

    A barreira prende todas as threads até a última chegar e as solta juntas; conferimos que
    todas passaram por ela (índices 0..N-1, um por thread) antes de olhar o resultado.
    """
    largada = threading.Barrier(len(donos), timeout=ESPERA_MAXIMA_S)
    passaram: list[int] = []

    def tentar(dono: Any) -> str:
        try:
            passaram.append(largada.wait())
            services.create_room(dono, "Nova")
            return "ok"
        except services.RoomError as erro:
            return erro.code
        finally:
            connection.close()

    with ThreadPoolExecutor(len(donos)) as pool:
        resultados = [f.result() for f in [pool.submit(tentar, d) for d in donos]]

    assert sorted(passaram) == list(range(len(donos)))  # premissa: todas largaram juntas
    return resultados


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
def test_donos_diferentes_com_uma_vaga_cada_criam_todos_sem_se_bloquear() -> None:
    """A trava é por usuário: a corrida de um dono não recusa nem atrasa o de outro."""
    donos = [criar_usuario(f"dono_{i}") for i in range(N)]
    for dono in donos:
        for i in range(rules.MAX_ROOMS_AS_OWNER - 1):
            services.create_room(dono, f"Sala {i}")
    assert [_salas_ativas(d) for d in donos] == [rules.MAX_ROOMS_AS_OWNER - 1] * N

    resultados = _largar(donos)

    assert resultados == ["ok"] * N
    assert [_salas_ativas(d) for d in donos] == [rules.MAX_ROOMS_AS_OWNER] * N
