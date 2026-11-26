"""`open_wallet` contra Postgres real: sem ciclo com a `system` e saldo inicial uma única vez.

Regra do ADR 0016: nenhuma operação trava uma carteira à mão antes de `post_entries`. O estado
testado (carteira que existe e ainda não recebeu o saldo inicial) não nasce no app; vem de
`jogador_sem_saldo_inicial`.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection

from apps.economy import audit, services
from apps.economy.models import TransactionKind, Wallet, WalletTransaction

from ..trades.test_trades_concurrency import _disputar
from .conftest import jogador_sem_saldo_inicial

N = 6

pytestmark = pytest.mark.django_db(transaction=True)


def test_open_wallet_nao_forma_ciclo_com_quem_trava_a_system_e_depois_a_carteira() -> None:
    """A vizinha faz o que a compra faz: segura a `system` e SÓ DEPOIS pede a carteira do jogador.

    Se `open_wallet` travar a carteira ANTES de pedir a `system` (o bug), ele segura a carteira
    esperando a `system`, a vizinha pede a carteira e o PostgreSQL aborta uma das duas
    (`deadlock detected`). Travando só o usuário, ele espera a `system` sem segurar carteira
    nenhuma, a vizinha termina e o saldo inicial entra.
    """
    jogador, carteira = jogador_sem_saldo_inicial("sem_saldo")
    sistema = Wallet.objects.get(kind="system")

    esperou, resultado = _disputar(
        trava=lambda: list(Wallet.objects.select_for_update().filter(pk=sistema.pk)),
        depois=lambda: list(Wallet.objects.select_for_update().filter(pk=carteira.pk)),
        operacao=lambda: services.open_wallet(jogador),
    )

    assert esperou, "open_wallet não esperou a trava da system"
    assert isinstance(resultado, Wallet)
    assert Wallet.objects.get(user=jogador).balance == 2_500
    assert audit.check_ledger() == []


def test_open_wallet_simultaneos_concedem_o_saldo_inicial_uma_unica_vez() -> None:
    jogador, _ = jogador_sem_saldo_inicial("corrida")
    largada = threading.Barrier(N)

    def abrir() -> str:
        try:
            largada.wait()
            services.open_wallet(jogador)
            return "ok"
        finally:
            connection.close()

    with ThreadPoolExecutor(N) as pool:
        resultados = [f.result() for f in [pool.submit(abrir) for _ in range(N)]]

    assert resultados == ["ok"] * N
    assert Wallet.objects.get(user=jogador).balance == 2_500
    concessoes = WalletTransaction.objects.filter(
        wallet__user=jogador, kind=TransactionKind.STARTING_GRANT
    )
    assert concessoes.count() == 1
    assert audit.check_ledger() == []
