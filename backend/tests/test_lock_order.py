"""Contrato da ordem de trava global (ADR 0016), lido do SQL que cada serviço emite.

A ordem é: jogadores, depois anúncio ou oferta, depois instâncias, depois carteiras. Uma operação
pega só um trecho dessa lista e nunca volta atrás. Ordem trocada entre duas operações é deadlock
(provado no PostgreSQL 17 do CI na Sessão 31); por isso o teste olha o `FOR UPDATE` que sai, e
não o texto do serviço: um helper pode esconder o `select_for_update`.

Determinístico, sem threads. Não prova a ausência de corrida real: isso é o papel de
`test_marketplace_locks.py`, `test_trades_concurrency.py` e
`test_marketplace_compra_concurrency.py`.
"""

import re
import uuid
from collections.abc import Callable
from itertools import groupby
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.economy import services as economy
from apps.economy.models import Wallet
from apps.marketplace import services as market
from apps.trades import services as trades

from .marketplace.conftest import criar_instancia, criar_skin, criar_usuario, tornar_amigos

pytestmark = pytest.mark.django_db

USUARIO = "accounts_user"
OFERTA = "trades_tradeoffer"
ANUNCIO = "marketplace_marketlisting"
INSTANCIA = "inventory_skininstance"
CARTEIRA = "economy_wallet"

# Posição de cada tabela na ordem global. Oferta e anúncio dividem o degrau: nenhuma operação
# trava os dois, e a compra trava só o anúncio.
POSICAO = {USUARIO: 0, OFERTA: 1, ANUNCIO: 1, INSTANCIA: 2, CARTEIRA: 3}

_FOR_UPDATE = re.compile(r"\bFOR (?:NO KEY )?UPDATE\b")
_TABELA = re.compile(r'\bFROM "(\w+)"')


def tabelas_travadas(operacao: Callable[[], Any]) -> list[str]:
    """As tabelas dos `SELECT ... FOR UPDATE` da operação, na ordem, sem repetição seguida."""
    with CaptureQueriesContext(connection) as captura:
        operacao()
    achadas: list[str] = []
    for consulta in captura.captured_queries:
        sql = consulta["sql"]
        if sql.lstrip().upper().startswith("SELECT") and _FOR_UPDATE.search(sql):
            tabela = _TABELA.search(sql)
            assert tabela is not None, sql
            achadas.append(tabela.group(1))
    return [tabela for tabela, _ in groupby(achadas)]


def respeita_a_ordem(tabelas: list[str]) -> bool:
    posicoes = [POSICAO[t] for t in tabelas]
    return posicoes == sorted(posicoes)


@pytest.fixture
def cena() -> SimpleNamespace:
    skin = criar_skin()
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    tornar_amigos(ana, bruno)
    return SimpleNamespace(
        ana=ana,
        bruno=bruno,
        a1=criar_instancia(ana, skin, "0.123456789"),
        b1=criar_instancia(bruno, skin, "0.250000000"),
    )


def _oferta(cena: SimpleNamespace) -> Any:
    return trades.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])


def _lancamento(cena: SimpleNamespace) -> Callable[[], Any]:
    """As carteiras são abertas ANTES da captura: aqui só o `post_entries` conta."""
    carteira = economy.ensure_wallet(cena.ana)
    sistema = economy.get_system_wallet()
    entradas = [economy.Entry(sistema.id, -100), economy.Entry(carteira.id, 100)]
    return lambda: economy.post_entries(entradas, kind="adjustment")


def test_o_detector_ve_a_ordem_invertida_e_a_repetida(cena: SimpleNamespace) -> None:
    """Prova de que o contrato não passa vazio: uma ordem plantada ao contrário é denunciada."""

    def invertida() -> None:
        with transaction.atomic():
            list(Wallet.objects.select_for_update().filter(user=cena.ana))
            list(User.objects.select_for_update().filter(pk=cena.ana.pk))

    achadas = tabelas_travadas(invertida)

    assert achadas == [CARTEIRA, USUARIO]
    assert not respeita_a_ordem(achadas)
    assert respeita_a_ordem([USUARIO, INSTANCIA, INSTANCIA, CARTEIRA])


def _criar_oferta(cena: SimpleNamespace) -> Callable[[], Any]:
    return lambda: _oferta(cena)


def _aceitar_oferta(cena: SimpleNamespace) -> Callable[[], Any]:
    oferta = _oferta(cena)
    return lambda: trades.accept_offer(cena.bruno, oferta.pk)


def _recusar_oferta(cena: SimpleNamespace) -> Callable[[], Any]:
    oferta = _oferta(cena)
    return lambda: trades.decline_offer(cena.bruno, oferta.pk)


def _cancelar_oferta(cena: SimpleNamespace) -> Callable[[], Any]:
    oferta = _oferta(cena)
    return lambda: trades.cancel_offer(cena.ana, oferta.pk)


def _criar_anuncio(cena: SimpleNamespace) -> Callable[[], Any]:
    return lambda: market.create_listing(cena.ana, cena.a1.pk, 1000)


def _cancelar_anuncio(cena: SimpleNamespace) -> Callable[[], Any]:
    anuncio = market.create_listing(cena.ana, cena.a1.pk, 1000)
    return lambda: market.cancel_listing(cena.ana, anuncio.pk)


def _comprar_anuncio(cena: SimpleNamespace) -> Callable[[], Any]:
    anuncio = market.create_listing(cena.ana, cena.a1.pk, 1000)
    chave = str(uuid.uuid4())
    return lambda: market.buy_listing(cena.bruno, anuncio.pk, idempotency_key=chave)


# Cada linha: "se o jogador faz X, o banco trava estas tabelas, nesta ordem".
CASOS: list[tuple[str, Callable[[SimpleNamespace], Callable[[], Any]], list[str]]] = [
    ("criar oferta de troca", _criar_oferta, [USUARIO, INSTANCIA]),
    ("aceitar oferta de troca", _aceitar_oferta, [USUARIO, OFERTA, INSTANCIA]),
    ("recusar oferta de troca", _recusar_oferta, [OFERTA]),
    ("cancelar oferta de troca", _cancelar_oferta, [OFERTA]),
    ("criar anúncio", _criar_anuncio, [USUARIO, INSTANCIA]),
    ("cancelar anúncio", _cancelar_anuncio, [ANUNCIO]),
    ("comprar anúncio", _comprar_anuncio, [USUARIO, ANUNCIO, INSTANCIA, CARTEIRA]),
    ("lançar no ledger", _lancamento, [CARTEIRA]),
]


@pytest.mark.parametrize(("nome", "montar", "esperado"), CASOS, ids=[c[0] for c in CASOS])
def test_cada_operacao_trava_na_ordem_global(
    cena: SimpleNamespace,
    nome: str,
    montar: Callable[[SimpleNamespace], Callable[[], Any]],
    esperado: list[str],
) -> None:
    achadas = tabelas_travadas(montar(cena))

    assert achadas == esperado, nome
    assert respeita_a_ordem(achadas), nome
