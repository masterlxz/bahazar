"""Concorrência das trocas contra PostgreSQL real: ofertas, aceites e ordem de trava.

Posse de item é área de risco (AGENTS §4): o que importa aqui é o INVARIANTE depois da corrida
(um dono por item, uma oferta pendente por item), não só que ninguém recebeu erro 500.
"""

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import connection, transaction

from apps.inventory.models import SkinInstance
from apps.trades import services
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_instancia, criar_usuario, tornar_amigos

N = 6
ESPERA_MAXIMA_S = 30

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


# --- duas ofertas com a mesma instância --------------------------------------------------------


def test_ofertas_diferentes_com_a_mesma_instancia_ao_mesmo_tempo_so_uma_vale(
    cena: SimpleNamespace,
) -> None:
    """a1 entra em N ofertas simultâneas (para bruno e para carla): uma vence, as outras recusam.

    Quem decide a corrida é o índice único parcial; o serviço traduz a violação em
    `ItemAlreadyOffered`, e as ofertas perdedoras não deixam linha nenhuma para trás.
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


def test_ofertas_em_ordem_oposta_nao_dao_deadlock(cena: SimpleNamespace) -> None:
    """Duas ofertas que disputam os mesmos três itens, listados em ordem oposta: sem deadlock.

    Os itens entram no banco em ordem de UUID, e o índice único espera a transação concorrente
    em vez de cruzar a espera. Resultado esperado: uma oferta, a outra recusada.
    """
    a1_a2, a2_a1 = [cena.a1.id, cena.a2.id], [cena.a2.id, cena.a1.id]

    resultados = _largar(
        [
            lambda: services.create_offer(cena.ana, cena.bruno, a1_a2, [cena.b1.id]),
            lambda: services.create_offer(cena.bruno, cena.ana, [cena.b1.id], a2_a1),
        ]
    )

    nomes = sorted(type(r).__name__ for r in resultados)
    assert nomes == ["ItemAlreadyOffered", "TradeOffer"]
    assert TradeOffer.objects.count() == 1
    assert TradeOfferItem.objects.filter(active=True).count() == 3


# --- aceites simultâneos -----------------------------------------------------------------------


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


def test_aceites_cruzados_do_mesmo_par_nao_dao_deadlock(cena: SimpleNamespace) -> None:
    """bruno aceita a oferta de ana enquanto ana aceita a de bruno: as duas valem, sem deadlock.

    Cada aceite trava o par de jogadores; sem a mesma ordem (por id) nos dois, as esperas
    cruzariam.
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


# --- ordem de trava das instâncias -------------------------------------------------------------


def _alguem_esperando_trava() -> bool:
    """Há algum pedido de trava na fila (não concedido)? Espera até a janela acabar."""
    limite = time.monotonic() + ESPERA_MAXIMA_S
    with connection.cursor() as cursor:
        while time.monotonic() < limite:
            cursor.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
            linha = cursor.fetchone()
            if linha and linha[0] > 0:
                return True
            time.sleep(0.05)
    return False


@pytest.mark.parametrize("menor_uuid_e_do", ["pedido", "oferecido"])
def test_aceite_trava_as_instancias_em_ordem_de_uuid(skin: Any, menor_uuid_e_do: str) -> None:
    """Prova da ordem de trava, de forma determinística.

    Ofertas pendentes nunca compartilham instância (o índice único proíbe), então o cruzamento
    real vem de OUTRA operação que trave as mesmas linhas (um trade-up, uma compra). Aqui o
    "vizinho" trava primeiro o item de MENOR UUID, espera o aceite entrar na fila da trava e só
    então pede o de maior UUID, como qualquer operação que siga a regra "em ordem de UUID".

    O aceite certo pede o menor primeiro: fica esperando o vizinho, que termina e solta tudo.
    Um aceite que travasse o maior antes (por exemplo, "oferecidos e depois pedidos") seguraria o
    maior e esperaria o menor, e o vizinho pediria o maior: deadlock. O teste varia qual lado
    tem o menor UUID para pegar as duas ordens erradas.
    """
    ana, bruno = criar_usuario("ana_01"), criar_usuario("bruno_02")
    tornar_amigos(ana, bruno)
    menor, maior = uuid.UUID(int=1), uuid.UUID(int=2**128 - 1)
    pk_ana, pk_bruno = (menor, maior) if menor_uuid_e_do == "oferecido" else (maior, menor)
    item_de_ana = criar_instancia(ana, skin, "0.1", pk=pk_ana)
    item_de_bruno = criar_instancia(bruno, skin, "0.2", pk=pk_bruno)
    oferta = services.create_offer(ana, bruno, [item_de_ana.id], [item_de_bruno.id])
    item_menor, item_maior = sorted((item_de_ana, item_de_bruno), key=lambda i: i.pk)
    segurando, soltar = threading.Event(), threading.Event()

    def vizinho() -> str:
        try:
            with transaction.atomic():
                list(SkinInstance.objects.select_for_update().filter(pk=item_menor.pk))
                segurando.set()
                assert soltar.wait(ESPERA_MAXIMA_S)
                list(SkinInstance.objects.select_for_update().filter(pk=item_maior.pk))
            return "ok"
        finally:
            connection.close()

    def aceitar() -> str:
        try:
            assert segurando.wait(ESPERA_MAXIMA_S)
            services.accept_offer(bruno, oferta.id)
            return "ok"
        finally:
            connection.close()

    with ThreadPoolExecutor(2) as pool:
        futuros = [pool.submit(vizinho), pool.submit(aceitar)]
        na_fila = _alguem_esperando_trava()
        soltar.set()
        resultados = [f.result(timeout=ESPERA_MAXIMA_S) for f in futuros]

    assert na_fila, "o aceite não chegou a esperar a trava do vizinho: o teste não provou nada"
    assert resultados == ["ok", "ok"]
    assert (_dono(item_de_ana), _dono(item_de_bruno)) == (bruno.id, ana.id)
