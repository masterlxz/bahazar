"""Concorrência do mercado contra PostgreSQL real: duas criações do mesmo item ao mesmo tempo.

Posse de item é área de risco (AGENTS §4): o que importa é o INVARIANTE depois da corrida (uma
instância, um anúncio ativo), não só que ninguém recebeu erro 500.
"""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import connection

from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketListing

from .conftest import nova_chave

ESPERA_MAXIMA_S = 30

pytestmark = pytest.mark.django_db(transaction=True)


def _largar(tarefas: Sequence[Callable[[], Any]]) -> list[Any]:
    """Roda cada tarefa numa thread, todas soltas juntas por uma barreira; devolve os resultados.

    Um erro de negócio (`MarketError`) vira o resultado, para o teste contar; qualquer outra
    exceção (deadlock, `IntegrityError` sem tradução) propaga e falha o teste. A conexão abre
    antes da barreira, para só a transação disputar.
    """
    largada = threading.Barrier(len(tarefas), timeout=ESPERA_MAXIMA_S)

    def rodar(tarefa: Callable[[], Any]) -> Any:
        try:
            connection.ensure_connection()
            largada.wait()
            return tarefa()
        except services.MarketError as erro:
            return erro
        finally:
            connection.close()

    with ThreadPoolExecutor(len(tarefas)) as pool:
        futuros = [pool.submit(rodar, t) for t in tarefas]
        return [f.result(timeout=ESPERA_MAXIMA_S) for f in futuros]


def test_duas_criacoes_simultaneas_do_mesmo_item_so_uma_vale(cena: SimpleNamespace) -> None:
    """O item trava na primeira transação; a segunda espera, vê o anúncio ativo e recusa.

    Corrida pura: um verde não prova a trava sozinho. A garantia de banco é provada à parte, em
    `test_marketplace_services.py` (checagem em Python desligada, índice único barra o INSERT).
    """
    precos = [111, 222]
    tarefas = [
        (
            lambda preco=preco: services.create_listing(
                cena.ana, cena.a1.pk, preco, idempotency_key=nova_chave()
            )
        )
        for preco in precos
    ]

    resultados = _largar(tarefas)

    nomes = sorted(type(r).__name__ for r in resultados)
    assert nomes == ["ItemAlreadyListed", "ListingOutcome"]
    ativos = MarketListing.objects.filter(instance=cena.a1, status=ListingStatus.ACTIVE)
    assert ativos.count() == 1
    assert ativos.get().price in precos
    assert MarketListing.objects.count() == 1
