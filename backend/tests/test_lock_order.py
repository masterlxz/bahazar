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
from apps.friends import services as friends
from apps.marketplace import services as market
from apps.trades import services as trades

from .economy.conftest import jogador_sem_saldo_inicial
from .marketplace.conftest import (
    anunciar,
    criar_instancia,
    criar_skin,
    criar_usuario,
    tornar_amigos,
)

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


def consultas_travadas(operacao: Callable[[], Any]) -> list[tuple[str, str]]:
    """`(tabela, sql)` de cada `SELECT ... FOR UPDATE` que a operação emite, na ordem."""
    with CaptureQueriesContext(connection) as captura:
        operacao()
    achadas: list[tuple[str, str]] = []
    for consulta in captura.captured_queries:
        sql = consulta["sql"]
        if sql.lstrip().upper().startswith("SELECT") and _FOR_UPDATE.search(sql):
            tabela = _TABELA.search(sql)
            assert tabela is not None, sql
            achadas.append((tabela.group(1), sql))
    return achadas


def tabelas_travadas(operacao: Callable[[], Any]) -> list[str]:
    """As tabelas dos `SELECT ... FOR UPDATE` da operação, na ordem, sem repetição seguida."""
    return [tabela for tabela, _ in groupby(t for t, _ in consultas_travadas(operacao))]


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


def _bloquear_com_oferta_pendente(cena: SimpleNamespace) -> Callable[[], Any]:
    """`friends.block` trava os jogadores e, pelo gancho, a oferta pendente do par."""
    _oferta(cena)
    return lambda: friends.block(cena.ana, cena.bruno.username)


def _desfazer_amizade_com_oferta_pendente(cena: SimpleNamespace) -> Callable[[], Any]:
    _oferta(cena)
    return lambda: friends.remove_friend(cena.ana, cena.bruno.username)


def _criar_anuncio(cena: SimpleNamespace) -> Callable[[], Any]:
    chave = str(uuid.uuid4())
    return lambda: market.create_listing(cena.ana, cena.a1.pk, 1000, idempotency_key=chave)


def _cancelar_anuncio(cena: SimpleNamespace) -> Callable[[], Any]:
    anuncio = anunciar(cena.ana, cena.a1)
    chave = str(uuid.uuid4())
    return lambda: market.cancel_listing(cena.ana, anuncio.pk, idempotency_key=chave)


def _resgatar_diaria(cena: SimpleNamespace) -> Callable[[], Any]:
    return lambda: economy.claim_daily(cena.ana)


def _abrir_carteira(cena: SimpleNamespace) -> Callable[[], Any]:
    """Carteira que existe e ainda não recebeu o saldo inicial (o app não a produz)."""
    jogador, _ = jogador_sem_saldo_inicial("sem_saldo")
    return lambda: economy.open_wallet(jogador)


def _comprar_anuncio(cena: SimpleNamespace) -> Callable[[], Any]:
    anuncio = anunciar(cena.ana, cena.a1)
    chave = str(uuid.uuid4())
    return lambda: market.buy_listing(cena.bruno, anuncio.pk, idempotency_key=chave)


def _transferir(cena: SimpleNamespace) -> Callable[[], Any]:
    chave = str(uuid.uuid4())
    return lambda: economy.transfer(cena.ana, cena.bruno, 100, idempotency_key=chave)


# Cada linha: "se o jogador faz X, o banco trava estas tabelas, nesta ordem".
CASOS: list[tuple[str, Callable[[SimpleNamespace], Callable[[], Any]], list[str]]] = [
    ("criar oferta de troca", _criar_oferta, [USUARIO, INSTANCIA]),
    ("aceitar oferta de troca", _aceitar_oferta, [USUARIO, OFERTA, INSTANCIA]),
    ("recusar oferta de troca", _recusar_oferta, [OFERTA]),
    ("cancelar oferta de troca", _cancelar_oferta, [OFERTA]),
    ("bloquear jogador com oferta pendente", _bloquear_com_oferta_pendente, [USUARIO, OFERTA]),
    (
        "desfazer amizade com oferta pendente",
        _desfazer_amizade_com_oferta_pendente,
        [USUARIO, OFERTA],
    ),
    ("criar anúncio", _criar_anuncio, [USUARIO, INSTANCIA]),
    ("cancelar anúncio", _cancelar_anuncio, [ANUNCIO]),
    ("comprar anúncio", _comprar_anuncio, [USUARIO, ANUNCIO, INSTANCIA, CARTEIRA]),
    ("transferir entre jogadores", _transferir, [USUARIO, CARTEIRA]),
    ("resgatar diária", _resgatar_diaria, [USUARIO, CARTEIRA]),
    ("abrir carteira", _abrir_carteira, [USUARIO, CARTEIRA]),
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


# As operações que travam VÁRIOS jogadores ou VÁRIAS carteiras de uma vez. Sem `ORDER BY`, o
# PostgreSQL trava na ordem em que lê as linhas, que costuma coincidir com a do id: o bug só
# apareceria com dois pedidos cruzados e ficaria verde quase sempre. Olhar o SQL emitido pega a
# ausência da ordem sem precisar de corrida. As instâncias não entram: lá a leitura de uma linha só
# já leva `ORDER BY` do `.first()`, o que tornaria a checagem vazia.
_COM_VARIAS_LINHAS = (
    "criar oferta de troca",
    "aceitar oferta de troca",
    "bloquear jogador com oferta pendente",
    "desfazer amizade com oferta pendente",
    "comprar anúncio",
    "transferir entre jogadores",
    "lançar no ledger",
)


@pytest.mark.parametrize("nome", _COM_VARIAS_LINHAS)
def test_a_trava_de_varios_jogadores_ou_carteiras_sai_ordenada_por_id(
    cena: SimpleNamespace, nome: str
) -> None:
    montar = next(m for n, m, _ in CASOS if n == nome)

    consultas = consultas_travadas(montar(cena))

    de_varias_linhas = [(t, sql) for t, sql in consultas if t in (USUARIO, CARTEIRA)]
    assert de_varias_linhas, nome
    for tabela, sql in de_varias_linhas:
        assert f'ORDER BY "{tabela}"."id"' in sql, (nome, sql)


@pytest.mark.parametrize(
    "nome",
    [
        "criar oferta de troca",
        "aceitar oferta de troca",
        "comprar anúncio",
        "transferir entre jogadores",
    ],
)
def test_a_checagem_de_is_active_le_o_banco_depois_de_travar_os_jogadores(
    cena: SimpleNamespace, nome: str
) -> None:
    """J4: a leitura de `is_active` vem DEPOIS do `FOR UPDATE` dos jogadores. Antes dele, uma
    desativação que confirma no meio deixaria a operação agir sobre um estado velho."""
    montar = next(m for n, m, _ in CASOS if n == nome)
    operacao = montar(cena)

    with CaptureQueriesContext(connection) as captura:
        operacao()

    sqls = [c["sql"] for c in captura.captured_queries]
    de_jogadores = [s for s in range(len(sqls)) if f'FROM "{USUARIO}"' in sqls[s]]
    trava = [s for s in de_jogadores if _FOR_UPDATE.search(sqls[s])]
    # `is_active` no WHERE: um SELECT de objeto inteiro também traz a coluna, e não é checagem.
    leitura = [
        s
        for s in de_jogadores
        if not _FOR_UPDATE.search(sqls[s])
        and " WHERE " in sqls[s]
        and '"is_active"' in sqls[s].split(" WHERE ", 1)[1]
    ]
    assert trava and leitura, nome
    assert trava[0] < leitura[0], nome


@pytest.mark.parametrize(
    "nome", ["bloquear jogador com oferta pendente", "desfazer amizade com oferta pendente"]
)
def test_o_gancho_do_par_trava_so_as_ofertas_pendentes_do_par_em_ordem_de_id(
    cena: SimpleNamespace, nome: str
) -> None:
    """O gancho pega VÁRIAS ofertas de uma vez: sem `ORDER BY`, duas operações do mesmo par
    (bloquear e outra que trave ofertas) poderiam esperar em ordem oposta. Só `pending` entra:
    travar a oferta resolvida bloquearia à toa quem a está lendo."""
    montar = next(m for n, m, _ in CASOS if n == nome)

    consultas = consultas_travadas(montar(cena))

    ofertas = [sql for tabela, sql in consultas if tabela == OFERTA]
    assert len(ofertas) == 1, nome
    assert 'ORDER BY "trades_tradeoffer"."id"' in ofertas[0], ofertas[0]
    filtro = ofertas[0].split(" WHERE ", 1)[1]  # depois do SELECT, que lista todas as colunas
    assert '"trades_tradeoffer"."status"' in filtro, ofertas[0]
