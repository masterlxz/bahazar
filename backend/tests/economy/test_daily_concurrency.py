"""Concorrência da diária contra Postgres real: pressa e clique duplo não duplicam dinheiro."""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from apps.economy import audit, services
from apps.economy.models import DailyClaim, Wallet

from ..trades.test_trades_concurrency import _disputar
from .conftest import T0, criar_usuario, system_com_id_baixo

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


def _jogador_com_carteira_depois_da_system() -> tuple[Any, Wallet]:
    """Um jogador cuja carteira tem `id` MAIOR que o da `system`.

    É a ordem em que a compra trava (carteiras por `id` crescente: `system`, depois a do jogador).
    Sem sorteio: a `system` nasce com `id` fixo e baixo ANTES do jogador (`system_com_id_baixo`).
    """
    jogador = criar_usuario("jogador_0")
    sistema = system_com_id_baixo()
    carteira = Wallet.objects.get(user=jogador)
    assert carteira.id > sistema.id
    return jogador, carteira


@pytest.mark.django_db(transaction=True)
def test_a_diaria_nao_forma_ciclo_com_quem_trava_a_system_e_depois_a_carteira() -> None:
    """A vizinha faz o que a compra faz: segura a `system` e SÓ DEPOIS pede a carteira do jogador.

    Se a diária travar a carteira do jogador ANTES de pedir a `system` (o bug), ela segura a
    carteira esperando a `system`, a vizinha pede a carteira e o PostgreSQL aborta uma das duas
    (`deadlock detected`, 500 para o jogador). Travando o usuário primeiro, a diária espera a
    `system` sem segurar carteira nenhuma, a vizinha termina e a diária credita.
    """
    jogador, carteira = _jogador_com_carteira_depois_da_system()
    sistema = Wallet.objects.get(kind="system")

    esperou, resultado = _disputar(
        trava=lambda: list(Wallet.objects.select_for_update().filter(pk=sistema.pk)),
        depois=lambda: list(Wallet.objects.select_for_update().filter(pk=carteira.pk)),
        operacao=lambda: services.claim_daily(jogador, now=T0),
    )

    assert esperou, "a diária não esperou a trava da system"
    assert isinstance(resultado, DailyClaim)
    assert Wallet.objects.get(user=jogador).balance == 2_750
    assert audit.check_ledger() == []
