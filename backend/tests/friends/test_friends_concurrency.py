"""Concorrência das amizades contra Postgres real: pedidos cruzados não duplicam nem travam."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection

from apps.friends import services
from apps.friends.models import Friendship

from .conftest import criar_usuario

N = 6


@pytest.mark.django_db(transaction=True)
def test_pedidos_cruzados_simultaneos_geram_uma_unica_relacao() -> None:
    """ana->bruno e bruno->ana ao mesmo tempo: uma linha só, sem deadlock, sem erro 500."""
    ana = criar_usuario("ana_01")
    bruno = criar_usuario("bruno_02")
    largada = threading.Barrier(N)

    def tentar(i: int) -> str:
        de, para = (ana, bruno) if i % 2 == 0 else (bruno, ana)
        try:
            largada.wait()
            services.send_request(de, para.username)
            return "ok"
        except services.FriendshipError:
            return "recusado"
        finally:
            connection.close()

    with ThreadPoolExecutor(N) as pool:
        resultados = [f.result() for f in [pool.submit(tentar, i) for i in range(N)]]

    assert sorted(resultados) == ["ok"] + ["recusado"] * (N - 1)
    assert Friendship.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_aceitar_e_bloquear_ao_mesmo_tempo_nunca_deixa_amizade_de_um_bloqueado() -> None:
    """Corrida entre bruno aceitando e ana bloqueando: o fim é sempre coerente.

    Ou a amizade nasce e o bloqueio a derruba depois, ou o bloqueio vem primeiro e o aceite
    falha. Nunca sobra uma linha `accepted` com o bloqueio já registrado.
    """
    ana = criar_usuario("ana_01")
    bruno = criar_usuario("bruno_02")
    pedido = services.send_request(ana, bruno.username)
    largada = threading.Barrier(2)

    def aceitar() -> None:
        try:
            largada.wait()
            services.accept_request(bruno, pedido.id)
        except services.FriendshipError:
            pass
        finally:
            connection.close()

    def bloquear() -> None:
        try:
            largada.wait()
            services.block(ana, bruno.username)
        finally:
            connection.close()

    with ThreadPoolExecutor(2) as pool:
        for f in [pool.submit(aceitar), pool.submit(bloquear)]:
            f.result()

    linhas = list(Friendship.objects.all())
    assert len(linhas) == 1
    assert linhas[0].status == "blocked"
    assert linhas[0].requester_id == ana.id
