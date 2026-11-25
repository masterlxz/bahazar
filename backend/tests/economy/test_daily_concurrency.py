"""Concorrência da diária contra Postgres real: pressa e clique duplo não duplicam dinheiro."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection

from apps.economy import audit, services
from apps.economy.models import DailyClaim, Wallet

from .conftest import T0, criar_usuario

N = 6


@pytest.mark.django_db(transaction=True)
def test_requisicoes_simultaneas_geram_um_unico_credito() -> None:
    ana = criar_usuario("ana_01")
    largada = threading.Barrier(N)

    def tentar() -> str:
        try:
            largada.wait()
            services.claim_daily(ana, now=T0)
            return "ok"
        except services.DailyNotReady:
            return "recusado"
        finally:
            connection.close()

    with ThreadPoolExecutor(N) as pool:
        resultados = [f.result() for f in [pool.submit(tentar) for _ in range(N)]]

    assert sorted(resultados) == ["ok"] + ["recusado"] * (N - 1)
    assert DailyClaim.objects.filter(user=ana).count() == 1
    assert Wallet.objects.get(user=ana).balance == 2_750
    assert audit.check_ledger() == []


@pytest.mark.django_db(transaction=True)
def test_cadastros_simultaneos_mantem_uma_unica_carteira_system() -> None:
    largada = threading.Barrier(N)

    def cadastrar(i: int) -> None:
        try:
            largada.wait()
            criar_usuario(f"jogador_{i}")
        finally:
            connection.close()

    with ThreadPoolExecutor(N) as pool:
        for f in [pool.submit(cadastrar, i) for i in range(N)]:
            f.result()

    assert Wallet.objects.filter(kind="system").count() == 1
    assert Wallet.objects.get(kind="system").balance == -2_500 * N
    assert audit.check_ledger() == []
