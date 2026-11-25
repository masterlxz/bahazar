"""Concorrência das trocas contra PostgreSQL real: ofertas, aceites e ordem de trava.

Posse de item é área de risco (AGENTS §4): o que importa aqui é o INVARIANTE depois da corrida
(um dono por item, uma oferta pendente por item), não só que ninguém recebeu erro 500.

Dois tipos de teste, e a diferença importa:
- corrida pura (`_largar`, N threads numa barreira): depende do agendamento; um verde não prova
  que a trava existe, só que esta intercalação não quebrou nada;
- disputa determinística (`_disputar`): uma transação "vizinha" segura uma trava, a operação
  testada roda noutra thread e o teste PROVA, pela fila em `pg_locks` do backend dela, que a
  operação esperou. A linha segurada usa `FOR NO KEY UPDATE` (`no_key=True`): com `FOR UPDATE`
  a FK do filho (KEY SHARE) bloquearia sozinha e o teste passaria SEM a trava do serviço.
"""

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import connection, transaction

from apps.accounts.models import User
from apps.friends import services as friends_services
from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance
from apps.trades import rules, services
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_instancia, criar_usuario, tornar_amigos

N = 6
ESPERA_MAXIMA_S = 30
JANELA_DA_FILA_S = 10

# UUIDs fixos: o menor e o maior possíveis. A ordem de trava é a de UUID, então o teste precisa
# saber qual vem primeiro, sem depender do `uuid4` do momento.
MENOR = uuid.UUID(int=1)
MAIOR = uuid.UUID(int=2**128 - 1)

_SQL_NA_FILA = "SELECT count(*) FROM pg_locks WHERE pid = %s AND NOT granted"

pytestmark = pytest.mark.django_db(transaction=True)


def _largar(tarefas: list[Callable[[], Any]]) -> list[Any]:
    """Roda cada tarefa numa thread, todas soltas juntas por uma barreira; devolve os resultados.

    Um erro de negócio (`TradeError`) vira o resultado, para o teste contar; qualquer outra
    exceção (deadlock, `IntegrityError` sem tradução) propaga e falha o teste. A conexão abre
    antes da barreira, para só a transação disputar.
    """
    largada = threading.Barrier(len(tarefas), timeout=ESPERA_MAXIMA_S)

    def rodar(tarefa: Callable[[], Any]) -> Any:
        try:
            connection.ensure_connection()
            largada.wait()
            return tarefa()
        except services.TradeError as erro:
            return erro
        finally:
            connection.close()

    with ThreadPoolExecutor(len(tarefas)) as pool:
        futuros = [pool.submit(rodar, t) for t in tarefas]
        return [f.result(timeout=ESPERA_MAXIMA_S) for f in futuros]


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


class _Disparo:
    """Roda `operacao` numa thread com conexão própria e sabe o pid do backend dela.

    A conexão desliga o índice e o bitmap (`enable_indexscan`/`enable_bitmapscan`): a leitura
    `WHERE pk IN (...)` vira varredura sequencial, que devolve as linhas na ordem em que foram
    GRAVADAS. Sem `ORDER BY`, o `FOR UPDATE` travaria nessa ordem; com `ORDER BY`, o Postgres
    ordena antes de travar. Os testes gravam o maior UUID primeiro, então tirar o `order_by` do
    serviço inverte a ordem de trava de forma certa, não por sorte do plano.

    `enable_indexonlyscan` NÃO é desligado: hoje é irrelevante, porque o Django seleciona todas
    as colunas e a varredura só de índice nunca se aplica. Se alguém trocar a leitura travada por
    `.only("pk")`, a premissa muda e esse parâmetro também precisa ser desligado aqui.
    """

    def __init__(self, pool: ThreadPoolExecutor, operacao: Callable[[], Any]) -> None:
        self.pid = 0
        self.conectada = threading.Event()
        self.futuro: Future[Any] = pool.submit(self._rodar, operacao)

    def _rodar(self, operacao: Callable[[], Any]) -> Any:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET enable_indexscan = off")
                cursor.execute("SET enable_bitmapscan = off")
                cursor.execute("SELECT pg_backend_pid()")
                linha = cursor.fetchone()
                assert linha is not None
                self.pid = linha[0]
            self.conectada.set()
            return operacao()
        except services.TradeError as erro:
            return erro
        finally:
            connection.close()

    def na_fila(self) -> bool:
        """O backend desta operação tem um pedido de trava não concedido (está esperando)?

        Filtra pelo pid dela: espera de outra sessão do servidor não conta. Se a operação
        terminar sem esperar nunca, devolve `False` na hora.
        """
        assert self.conectada.wait(ESPERA_MAXIMA_S)
        limite = time.monotonic() + JANELA_DA_FILA_S
        with connection.cursor() as cursor:
            while time.monotonic() < limite and not self.futuro.done():
                cursor.execute(_SQL_NA_FILA, [self.pid])
                linha = cursor.fetchone()
                if linha and linha[0] > 0:
                    return True
                time.sleep(0.05)
        return False


def _segurar(
    pool: ThreadPoolExecutor,
    trava: Callable[[], Any],
    depois: Callable[[], Any],
    segurando: threading.Event,
    soltar: threading.Event,
) -> Future[str]:
    """Transação vizinha: toma `trava`, espera o sinal, roda `depois` e comita."""

    def rodar() -> str:
        try:
            with transaction.atomic():
                trava()
                segurando.set()
                assert soltar.wait(ESPERA_MAXIMA_S)
                depois()
            return "ok"
        finally:
            connection.close()

    return pool.submit(rodar)


def _disputar(
    *, trava: Callable[[], Any], depois: Callable[[], Any], operacao: Callable[[], Any]
) -> tuple[bool, Any]:
    """Uma vizinha segura `trava`; `operacao` roda noutra thread; devolve `(esperou, resultado)`.

    `esperou` é a prova de que a operação pediu uma trava em conflito com a da vizinha. Depois
    de soltar, a vizinha roda `depois` (por exemplo, pedir outra linha, que daria deadlock se a
    operação estivesse segurando essa) e comita. Erro da vizinha ou da operação propaga.
    """
    segurando, soltar = threading.Event(), threading.Event()
    with ThreadPoolExecutor(2) as pool:
        vizinha = _segurar(pool, trava, depois, segurando, soltar)
        try:
            assert segurando.wait(ESPERA_MAXIMA_S)
            disparo = _Disparo(pool, operacao)
            esperou = disparo.na_fila()
        finally:
            soltar.set()
        resultado = disparo.futuro.result(timeout=ESPERA_MAXIMA_S)
        assert vizinha.result(timeout=ESPERA_MAXIMA_S) == "ok"
    return esperou, resultado


def _travar_instancia(instancia: Any) -> None:
    list(SkinInstance.objects.select_for_update(no_key=True).filter(pk=instancia.pk))


def _travar_usuarios(*usuarios: Any) -> None:
    ids = [u.pk for u in usuarios]
    list(User.objects.select_for_update(no_key=True).filter(pk__in=ids))


# --- duas ofertas com a mesma instância --------------------------------------------------------


def test_ofertas_diferentes_com_a_mesma_instancia_ao_mesmo_tempo_so_uma_vale(
    cena: SimpleNamespace,
) -> None:
    """a1 entra em N ofertas simultâneas (para bruno e para carla): uma vence, as outras recusam.

    Corrida pura. Quem serializa é a trava dos jogadores e das instâncias; a segunda criação, ao
    obter a trava, vê a instância ocupada e recusa. O índice único é só rede de segurança aqui:
    a prova de que ele fecha a corrida sozinho está em `test_trades_services.py`
    (`test_o_indice_unico_do_banco_fecha_a_corrida_...`), que desliga as checagens em Python.
    """
    tornar_amigos(cena.carla, cena.ana)
    destinos = [(cena.bruno, cena.b1), (cena.carla, cena.c1)]

    def propor(i: int) -> Callable[[], Any]:
        para, pedido = destinos[i % 2]
        return lambda: services.create_offer(cena.ana, para, [cena.a1.id], [pedido.id])

    resultados = _largar([propor(i) for i in range(N)])

    nomes = sorted(type(r).__name__ for r in resultados)
    assert nomes == ["ItemAlreadyOffered"] * (N - 1) + ["TradeOffer"]
    assert TradeOffer.objects.count() == 1
    assert TradeOfferItem.objects.count() == 2
    assert TradeOfferItem.objects.filter(instance=cena.a1, active=True).count() == 1


def test_criacoes_simultaneas_do_mesmo_proponente_respeitam_o_teto_de_pendentes(
    cena: SimpleNamespace, skin: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Teto 2 com N pedidos juntos: exatamente 2 entram.

    Corrida pura (não prova a trava sozinha): a contagem de pendentes é lida com a linha do
    proponente travada, e é isso que impede dois pedidos de verem "só 1 pendente" ao mesmo tempo.
    """
    monkeypatch.setattr(rules, "MAX_PENDING_PER_PROPOSER", 2)
    dar = [criar_instancia(cena.ana, skin) for _ in range(N)]
    pedir = [criar_instancia(cena.bruno, skin) for _ in range(N)]

    def propor(i: int) -> Callable[[], Any]:
        return lambda: services.create_offer(cena.ana, cena.bruno, [dar[i].id], [pedir[i].id])

    resultados = _largar([propor(i) for i in range(N)])

    nomes = sorted(type(r).__name__ for r in resultados)
    assert nomes == ["TooManyPendingOffers"] * (N - 2) + ["TradeOffer"] * 2
    assert TradeOffer.objects.filter(status="pending").count() == 2


# --- a criação revalida sob trava --------------------------------------------------------------


def test_criar_detecta_a_troca_de_dono_ocorrida_enquanto_esperava_a_trava(
    cena: SimpleNamespace,
) -> None:
    """Uma vizinha segura a1, passa a1 para carla e comita; a criação já estava na fila.

    Se a criação lesse o dono ANTES da trava (ou sem trava), veria ana e gravaria uma oferta
    obsoleta. Lendo sob trava, vê carla e recusa.
    """
    esperou, resultado = _disputar(
        trava=lambda: _travar_instancia(cena.a1),
        depois=lambda: inventory_services.change_owner(
            cena.a1.id, from_owner=cena.ana, to_owner=cena.carla
        ),
        operacao=lambda: services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id]),
    )

    assert esperou, "a criação não esperou a trava da instância"
    assert isinstance(resultado, services.ItemNotOwned)
    assert _dono(cena.a1) == cena.carla.id
    assert TradeOffer.objects.count() == 0


# --- ordem de trava das instâncias (criar e aceitar) --------------------------------------------


def _gravar_maior_primeiro(skin: Any, donos: dict[uuid.UUID, Any]) -> dict[uuid.UUID, Any]:
    """Cria os itens com UUID fixo, o MAIOR primeiro: é a ordem física que o teste explora."""
    return {pk: criar_instancia(donos[pk], skin, pk=pk) for pk in (MAIOR, MENOR)}


@pytest.mark.parametrize("menor_e_do", ["proponente", "destinatario"])
def test_criar_trava_as_instancias_em_ordem_de_uuid(skin: Any, menor_e_do: str) -> None:
    """A vizinha segura o item de MENOR UUID e só depois pede o de maior, como manda a regra.

    A criação certa pede o menor primeiro: espera sem segurar nada, e a vizinha termina. Uma que
    travasse o maior antes (leitura na ordem física, sem `order_by`, ou "oferecidos e depois
    pedidos") esperaria o menor segurando o maior: a vizinha pediria o maior e daria deadlock.
    """
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    tornar_amigos(ana, bruno)
    pk_ana, pk_bruno = (MENOR, MAIOR) if menor_e_do == "proponente" else (MAIOR, MENOR)
    itens = _gravar_maior_primeiro(skin, {pk_ana: ana, pk_bruno: bruno})
    dar, pedir = [itens[pk_ana].id], [itens[pk_bruno].id]

    esperou, resultado = _disputar(
        trava=lambda: _travar_instancia(itens[MENOR]),
        depois=lambda: _travar_instancia(itens[MAIOR]),
        operacao=lambda: services.create_offer(ana, bruno, dar, pedir),
    )

    assert esperou, "a criação não esperou a trava do item de menor UUID"
    assert isinstance(resultado, TradeOffer)


@pytest.mark.parametrize("menor_e_do", ["proponente", "destinatario"])
def test_aceite_trava_as_instancias_em_ordem_de_uuid(skin: Any, menor_e_do: str) -> None:
    """Mesma prova da criação, para o aceite (que revalida e troca os donos)."""
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    tornar_amigos(ana, bruno)
    pk_ana, pk_bruno = (MENOR, MAIOR) if menor_e_do == "proponente" else (MAIOR, MENOR)
    itens = _gravar_maior_primeiro(skin, {pk_ana: ana, pk_bruno: bruno})
    oferta = services.create_offer(ana, bruno, [itens[pk_ana].id], [itens[pk_bruno].id])

    esperou, resultado = _disputar(
        trava=lambda: _travar_instancia(itens[MENOR]),
        depois=lambda: _travar_instancia(itens[MAIOR]),
        operacao=lambda: services.accept_offer(bruno, oferta.id),
    )

    assert esperou, "o aceite não esperou a trava do item de menor UUID"
    assert isinstance(resultado, TradeOffer)
    assert (_dono(itens[pk_ana]), _dono(itens[pk_bruno])) == (bruno.id, ana.id)


# --- ordem de trava dos jogadores --------------------------------------------------------------


@pytest.mark.parametrize("operacao", ["criar", "aceitar"])
def test_trava_dos_jogadores_e_em_ordem_de_id(skin: Any, operacao: str) -> None:
    """A vizinha segura o jogador de MENOR id e só depois pede o de maior: sem deadlock.

    O proponente é o jogador de MAIOR id, de propósito: quem travasse "proponente e depois
    destinatário" (ou lesse na ordem física, o maior foi gravado primeiro) seguraria o maior e
    esperaria o menor, e a vizinha pediria o maior. Vale para criar e para aceitar.
    """
    maior = criar_usuario("maior_01", pk=MAIOR)
    menor = criar_usuario("menor_02", pk=MENOR)
    tornar_amigos(maior, menor)
    m1, m2 = criar_instancia(maior, skin), criar_instancia(maior, skin)
    n1, n2 = criar_instancia(menor, skin), criar_instancia(menor, skin)
    oferta = services.create_offer(maior, menor, [m1.id], [n1.id])

    def criar_outra() -> Any:
        return services.create_offer(maior, menor, [m2.id], [n2.id])

    def aceitar() -> Any:
        return services.accept_offer(menor, oferta.id)

    executar = criar_outra if operacao == "criar" else aceitar

    esperou, resultado = _disputar(
        trava=lambda: _travar_usuarios(menor),
        depois=lambda: _travar_usuarios(maior),
        operacao=executar,
    )

    assert esperou, "a operação não esperou a trava do jogador de menor id"
    assert isinstance(resultado, TradeOffer)


def test_aceite_espera_quem_segura_os_jogadores_e_depois_ve_a_amizade_desfeita(
    cena: SimpleNamespace,
) -> None:
    """Aceitar x desfazer a amizade no mesmo par (`friends.services`), de forma determinística.

    A vizinha segura os dois jogadores, desfaz a amizade e só então comita. O aceite tem de
    ESPERAR na trava dos jogadores (provado pela fila do pid dele) e, ao acordar, ver a amizade
    já desfeita: falha com `NotFriends` e nada muda de dono. Sem a trava dos jogadores o aceite
    não esperaria, leria a amizade ainda viva e trocaria os itens.
    """
    oferta = services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])

    esperou, resultado = _disputar(
        trava=lambda: _travar_usuarios(cena.ana, cena.bruno),
        depois=lambda: friends_services.remove_friend(cena.ana, cena.bruno.username),
        operacao=lambda: services.accept_offer(cena.bruno, oferta.id),
    )

    assert esperou, "o aceite não esperou a trava dos jogadores"
    assert isinstance(resultado, services.NotFriends)
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.id, cena.bruno.id)
    assert TradeOffer.objects.get(pk=oferta.pk).status == "pending"


# --- revalidação SOB trava (caracterização: o código já faz isto) --------------------------------


@pytest.mark.parametrize("mudanca", ["dono", "consumo"])
def test_aceite_confere_dono_e_consumo_sob_a_trava_das_instancias(
    cena: SimpleNamespace, mudanca: str
) -> None:
    """A vizinha segura a1 e, antes de comitar, muda o dono ou consome o item; o aceite esperava.

    O aceite tem de ler dono e consumo DEPOIS de obter a trava e recusar com o erro DA TROCA
    (`ItemNotOwned`/`ItemConsumed`), sem mover nada. Mutação que derruba este teste: tirar o
    `select_for_update()` da leitura das instâncias em `accept_offer`. O aceite então leria a1
    sem esperar ou com o dono antigo, e o erro viria de dentro de `change_owner` (de
    `inventory`, não de `trades`).
    """
    oferta = services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])

    def trocar_dono() -> None:
        # Por fora da porta: o `change_owner` recusa item em oferta pendente (`ItemLocked`).
        SkinInstance.objects.filter(pk=cena.a1.pk).update(owner=cena.carla)

    def consumir() -> None:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(consumed_at=datetime.now(UTC))

    esperou, resultado = _disputar(
        trava=lambda: _travar_instancia(cena.a1),
        depois=trocar_dono if mudanca == "dono" else consumir,
        operacao=lambda: services.accept_offer(cena.bruno, oferta.id),
    )

    esperado = services.ItemNotOwned if mudanca == "dono" else services.ItemConsumed
    dono_de_a1 = cena.carla.id if mudanca == "dono" else cena.ana.id
    assert esperou, "o aceite não esperou a trava da instância"
    assert type(resultado) is esperado
    assert (_dono(cena.a1), _dono(cena.b1)) == (dono_de_a1, cena.bruno.id)
    assert TradeOffer.objects.get(pk=oferta.pk).status == "pending"


def test_criar_confere_a_amizade_sob_a_trava_dos_jogadores(cena: SimpleNamespace) -> None:
    """A vizinha segura os jogadores e desfaz a amizade antes de comitar; a criação esperava.

    Mutação que derruba este teste: mover `can_view` para ANTES de `_travar_jogadores` em
    `create_offer`. A criação leria a amizade ainda viva, esperaria a trava e gravaria a oferta
    em vez de falhar com `NotFriends`.
    """
    esperou, resultado = _disputar(
        trava=lambda: _travar_usuarios(cena.ana, cena.bruno),
        depois=lambda: friends_services.remove_friend(cena.ana, cena.bruno.username),
        operacao=lambda: services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id]),
    )

    assert esperou, "a criação não esperou a trava dos jogadores"
    assert type(resultado) is services.NotFriends
    assert TradeOffer.objects.count() == 0


def test_criar_confere_o_teto_de_pendentes_sob_a_trava_dos_jogadores(
    cena: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vizinha segura os jogadores e abre a 1a oferta de ana (teto 1); a criação esperava.

    Mutação que derruba este teste: mover `selectors.pending_count` para ANTES de
    `_travar_jogadores` em `create_offer`. A criação contaria 0 pendentes, esperaria a trava e
    gravaria a oferta em vez de falhar com `TooManyPendingOffers`.
    """
    monkeypatch.setattr(rules, "MAX_PENDING_PER_PROPOSER", 1)

    def abrir_outra() -> None:
        services.create_offer(cena.ana, cena.bruno, [cena.a2.id], [cena.b2.id])

    esperou, resultado = _disputar(
        trava=lambda: _travar_usuarios(cena.ana, cena.bruno),
        depois=abrir_outra,
        operacao=lambda: services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id]),
    )

    assert esperou, "a criação não esperou a trava dos jogadores"
    assert type(resultado) is services.TooManyPendingOffers
    assert TradeOffer.objects.count() == 1


# --- aceites simultâneos (corrida pura) --------------------------------------------------------


def test_aceites_simultaneos_da_mesma_oferta_trocam_os_itens_uma_unica_vez(
    cena: SimpleNamespace,
) -> None:
    oferta = services.create_offer(cena.ana, cena.bruno, [cena.a1.id, cena.a2.id], [cena.b1.id])

    resultados = _largar([lambda: services.accept_offer(cena.bruno, oferta.id) for _ in range(N)])

    nomes = sorted(type(r).__name__ for r in resultados)
    assert nomes == ["OfferNotPending"] * (N - 1) + ["TradeOffer"]
    donos = [_dono(i) for i in (cena.a1, cena.a2, cena.b1)]
    assert donos == [cena.bruno.id, cena.bruno.id, cena.ana.id]
    assert TradeOffer.objects.get(pk=oferta.pk).status == "accepted"
    assert SkinInstance.objects.count() == 5


def test_aceitar_e_cancelar_ao_mesmo_tempo_terminam_coerentes(cena: SimpleNamespace) -> None:
    """Aceite vence: os donos trocam. Cancelamento vence: ninguém muda. Nunca os dois."""
    oferta = services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])

    resultados = _largar(
        [
            lambda: services.accept_offer(cena.bruno, oferta.id),
            lambda: services.cancel_offer(cena.ana, oferta.id),
        ]
    )

    nomes = sorted(type(r).__name__ for r in resultados)
    assert nomes == ["OfferNotPending", "TradeOffer"]
    estado = TradeOffer.objects.get(pk=oferta.pk).status
    donos = [_dono(cena.a1), _dono(cena.b1)]
    if estado == "accepted":
        assert donos == [cena.bruno.id, cena.ana.id]
    else:
        assert estado == "cancelled"
        assert donos == [cena.ana.id, cena.bruno.id]
    assert not TradeOfferItem.objects.filter(offer=oferta, active=True).exists()


def test_aceites_cruzados_do_mesmo_par_terminam_os_dois(cena: SimpleNamespace) -> None:
    """Fumaça: duas ofertas independentes do mesmo par, aceitas ao mesmo tempo, valem as duas.

    NÃO prova a ordem de trava dos jogadores (as instâncias são disjuntas e a intercalação não
    é controlada): essa prova é `test_trava_dos_jogadores_e_em_ordem_de_id`.
    """
    de_ana = services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])
    de_bruno = services.create_offer(cena.bruno, cena.ana, [cena.b2.id], [cena.a2.id])

    resultados = _largar(
        [
            lambda: services.accept_offer(cena.bruno, de_ana.id),
            lambda: services.accept_offer(cena.ana, de_bruno.id),
        ]
    )

    assert [type(r).__name__ for r in resultados] == ["TradeOffer", "TradeOffer"]
    donos = [_dono(i) for i in (cena.a1, cena.a2, cena.b1, cena.b2)]
    assert donos == [cena.bruno.id, cena.bruno.id, cena.ana.id, cena.ana.id]


def test_criar_e_aceitar_ao_mesmo_tempo_no_mesmo_par_terminam_os_dois(
    cena: SimpleNamespace,
) -> None:
    """Fumaça: bruno aceita a oferta de ana enquanto cria outra para ela; nenhum falha.

    Corrida pura, sem prova de ordem de trava (essa é do teste determinístico acima).
    """
    de_ana = services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])

    resultados = _largar(
        [
            lambda: services.accept_offer(cena.bruno, de_ana.id),
            lambda: services.create_offer(cena.bruno, cena.ana, [cena.b2.id], [cena.a2.id]),
        ]
    )

    assert sorted(type(r).__name__ for r in resultados) == ["TradeOffer", "TradeOffer"]
    assert TradeOffer.objects.get(pk=de_ana.pk).status == "accepted"
    assert TradeOffer.objects.filter(status="pending").count() == 1
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.bruno.id, cena.ana.id)
    assert (_dono(cena.a2), _dono(cena.b2)) == (cena.ana.id, cena.bruno.id)
