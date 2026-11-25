"""API das trocas de itens: criar, aceitar, recusar, cancelar e ler, tudo com `Idempotency-Key`.

Cena (conftest): ana e bruno são amigos; carla não é amiga de ninguém. ana tem a1 (float
0,123456789) e a2; bruno tem b1 e b2; carla tem c1. O cenário é montado pela API sempre que o
teste não for sobre o próprio passo de montagem.
"""

import json
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.economy.models import IdempotencyRecord
from apps.friends.models import Friendship
from apps.inventory.models import SkinInstance
from apps.inventory.services import ItemLocked
from apps.trades import rules, services, views
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_instancia, criar_skin, tornar_amigos

TRADES_URL = "/api/v1/trades/"
CABECALHO = "Idempotency-Key"
UM_ID_QUALQUER = "7c0f8e1a-0000-4000-8000-000000000001"
N = 6
ESPERA_MAXIMA_S = 30

pytestmark = pytest.mark.django_db


def _url(offer_id: Any, acao: str = "") -> str:
    return f"{TRADES_URL}{offer_id}/{acao}/" if acao else f"{TRADES_URL}{offer_id}/"


def _logado(usuario: Any) -> APIClient:
    client = APIClient()
    client.force_authenticate(usuario)
    return client


def _nova_chave() -> str:
    return str(uuid.uuid4())


def _post(cliente: APIClient, url: str, corpo: Any, chave: str | None) -> Any:
    headers = {CABECALHO: chave} if chave is not None else {}
    return cliente.post(url, corpo, format="json", headers=headers)


def _corpo(destino: str, oferecidos: Sequence[Any], pedidos: Sequence[Any]) -> dict[str, Any]:
    return {
        "recipient": destino,
        "offered": [str(i.pk) for i in oferecidos],
        "requested": [str(i.pk) for i in pedidos],
    }


def _criar(cliente: APIClient, corpo: Any, chave: str | None = None) -> Any:
    return _post(cliente, TRADES_URL, corpo, chave or _nova_chave())


def _criada(cliente: APIClient, corpo: Any) -> dict[str, Any]:
    resposta = _criar(cliente, corpo)
    assert resposta.status_code == 201, resposta.content
    dados: dict[str, Any] = resposta.json()
    return dados


def _agir(cliente: APIClient, offer_id: Any, acao: str, chave: str | None = None) -> Any:
    return _post(cliente, _url(offer_id, acao), {}, chave or _nova_chave())


def _a1_por_b1(cena: SimpleNamespace) -> dict[str, Any]:
    """ana oferece a1 e pede b1 a bruno, pela API."""
    return _criada(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b1]))


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def _chaves_do_json(valor: Any) -> set[str]:
    """Todas as chaves de objeto, em qualquer profundidade."""
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _chaves_do_json(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _chaves_do_json(v)}
    return set()


def _resumo(resposta: Any) -> tuple[int, Any]:
    return resposta.status_code, resposta.json()


# --- autenticação ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "url"),
    [
        ("GET", TRADES_URL),
        ("POST", TRADES_URL),
        ("GET", _url(UM_ID_QUALQUER)),
        ("POST", _url(UM_ID_QUALQUER, "accept")),
        ("POST", _url(UM_ID_QUALQUER, "decline")),
        ("POST", _url(UM_ID_QUALQUER, "cancel")),
    ],
)
def test_anonimo_nao_acessa_nenhuma_rota(metodo: str, url: str) -> None:
    resposta = APIClient().generic(metodo, url, headers={CABECALHO: _nova_chave()})

    assert resposta.status_code in (401, 403)


@pytest.mark.parametrize(
    ("metodo", "url"),
    [
        ("DELETE", TRADES_URL),
        ("PUT", TRADES_URL),
        ("DELETE", _url(UM_ID_QUALQUER)),
        ("POST", _url(UM_ID_QUALQUER)),
        ("GET", _url(UM_ID_QUALQUER, "accept")),
    ],
)
def test_metodos_fora_do_contrato_sao_recusados(
    cena: SimpleNamespace, metodo: str, url: str
) -> None:
    resposta = _logado(cena.ana).generic(metodo, url, headers={CABECALHO: _nova_chave()})

    assert resposta.status_code == 405


# --- fluxo feliz ----------------------------------------------------------------------------


def test_criar_devolve_201_com_a_oferta_e_nada_muda_de_dono(cena: SimpleNamespace) -> None:
    resposta = _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b2]))

    assert resposta.status_code == 201
    oferta = resposta.json()
    assert oferta["status"] == "pending"
    assert oferta["resolved_at"] is None
    assert oferta["proposer"]["username"] == "ana_01"
    assert oferta["recipient"]["username"] == "bruno_02"
    por_lado = {i["side"]: i for i in oferta["items"]}
    assert set(por_lado) == {"offered", "requested"}
    assert por_lado["offered"]["id"] == str(cena.a1.pk)
    assert por_lado["offered"]["float_value"] == "0.123456789"
    assert por_lado["offered"]["wear"] == "Minimal Wear"
    assert por_lado["offered"]["reference_price"] == 1000
    assert por_lado["offered"]["skin"]["name"] == cena.a1.skin.name
    assert por_lado["requested"]["id"] == str(cena.b2.pk)
    assert por_lado["requested"]["float_value"] == "0.750000000"
    assert por_lado["requested"]["wear"] == "Battle-Scarred"  # cortes de inventory/rules.py
    assert TradeOffer.objects.filter(pk=oferta["id"], status="pending").count() == 1
    assert (_dono(cena.a1), _dono(cena.b2)) == (cena.ana.pk, cena.bruno.pk)  # só propôs


def test_o_corpo_da_oferta_tem_so_os_campos_publicos(cena: SimpleNamespace) -> None:
    resposta = _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b1]))

    oferta = resposta.json()
    assert set(oferta) == {
        "id",
        "status",
        "created_at",
        "resolved_at",
        "proposer",
        "recipient",
        "items",
    }
    assert set(oferta["proposer"]) == set(oferta["recipient"]) == {"username", "avatar"}
    assert all(
        set(i) == {"side", "id", "skin", "float_value", "wear", "reference_price"}
        for i in oferta["items"]
    )
    assert set(oferta["items"][0]["skin"]) == {"id", "name", "weapon", "rarity", "collection"}
    internos = {"email", "active", "acquired_via", "consumed_at", "owner", "password"}
    assert _chaves_do_json(oferta).isdisjoint(internos)
    assert "@exemplo.com" not in resposta.content.decode()


def test_o_destinatario_aceita_e_os_donos_trocam_de_fato(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)

    resposta = _agir(_logado(cena.bruno), oferta["id"], "accept")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["id"] == oferta["id"]
    assert corpo["status"] == "accepted"
    assert corpo["resolved_at"] is not None
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.bruno.pk, cena.ana.pk)
    # o que não estava na oferta continua com o dono de antes, e o float não é tocado
    assert (_dono(cena.a2), _dono(cena.b2), _dono(cena.c1)) == (
        cena.ana.pk,
        cena.bruno.pk,
        cena.carla.pk,
    )
    assert SkinInstance.objects.get(pk=cena.a1.pk).float_value == Decimal("0.123456789")
    assert TradeOfferItem.objects.filter(active=True).count() == 0


@pytest.mark.parametrize(
    ("quem", "acao", "estado"),
    [("bruno", "decline", "declined"), ("ana", "cancel", "cancelled")],
)
def test_recusar_e_cancelar_liberam_as_instancias(
    cena: SimpleNamespace, quem: str, acao: str, estado: str
) -> None:
    oferta = _a1_por_b1(cena)

    resposta = _agir(_logado(getattr(cena, quem)), oferta["id"], acao)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == estado
    assert resposta.json()["resolved_at"] is not None
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)
    assert TradeOfferItem.objects.filter(active=True).count() == 0
    # as mesmas instâncias já cabem numa oferta nova
    nova = _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b1]))
    assert nova.status_code == 201


def test_quem_ja_resolveu_nao_resolve_de_novo_com_outra_chave(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    assert _agir(_logado(cena.bruno), oferta["id"], "accept").status_code == 200

    segunda = _agir(_logado(cena.bruno), oferta["id"], "accept")

    assert segunda.status_code == 409
    assert segunda.json()["code"] == "offer_not_pending"
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.bruno.pk, cena.ana.pk)  # trocou uma vez só


# --- idempotência ---------------------------------------------------------------------------


def test_mesma_chave_e_mesmo_corpo_repete_a_resposta_sem_criar_outra_oferta(
    cena: SimpleNamespace,
) -> None:
    chave = _nova_chave()
    corpo = _corpo("bruno_02", [cena.a1], [cena.b1])

    primeira = _criar(_logado(cena.ana), corpo, chave)
    segunda = _criar(_logado(cena.ana), corpo, chave)

    assert (primeira.status_code, segunda.status_code) == (201, 201)
    assert segunda.json() == primeira.json()
    assert TradeOffer.objects.count() == 1
    assert TradeOfferItem.objects.count() == 2
    assert IdempotencyRecord.objects.count() == 1


def test_a_ordem_dos_ids_no_corpo_nao_muda_o_pedido(cena: SimpleNamespace) -> None:
    chave = _nova_chave()
    ana = _logado(cena.ana)

    primeira = _criar(ana, _corpo("bruno_02", [cena.a1, cena.a2], [cena.b1, cena.b2]), chave)
    invertida = _criar(ana, _corpo("bruno_02", [cena.a2, cena.a1], [cena.b2, cena.b1]), chave)

    assert primeira.status_code == 201
    assert invertida.status_code == 201  # replay, não 422
    assert invertida.json() == primeira.json()
    assert TradeOffer.objects.count() == 1


def test_a_forma_do_nome_e_do_uuid_nao_muda_o_pedido(cena: SimpleNamespace) -> None:
    chave = _nova_chave()
    ana = _logado(cena.ana)
    primeira = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.b1]), chave)
    outra_forma = {
        "recipient": "  BRUNO_02 ",
        "offered": [cena.a1.pk.hex],
        "requested": [str(cena.b1.pk).upper()],
    }

    segunda = _criar(ana, outra_forma, chave)

    assert segunda.status_code == 201
    assert segunda.json() == primeira.json()
    assert TradeOffer.objects.count() == 1


def test_mesma_chave_com_outro_pedido_da_422_e_nao_cria_nada(cena: SimpleNamespace) -> None:
    chave = _nova_chave()
    ana = _logado(cena.ana)
    primeira = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.b1]), chave)

    outro = _criar(ana, _corpo("bruno_02", [cena.a2], [cena.b2]), chave)

    assert primeira.status_code == 201
    assert outro.status_code == 422
    assert outro.json()["code"] == "idempotency_key_reused"
    assert TradeOffer.objects.count() == 1
    assert set(TradeOfferItem.objects.values_list("instance_id", flat=True)) == {
        cena.a1.pk,
        cena.b1.pk,
    }


def test_mesma_chave_e_mesmas_listas_com_outro_destinatario_da_422(cena: SimpleNamespace) -> None:
    """O destinatário faz parte do pedido: sem ele no hash, isto seria um replay do 201.

    carla vira amiga de ana e recebe os MESMOS ids (os itens pedidos são do bruno). Se o pedido
    chegasse ao serviço, a resposta seria `item_not_owned`; a idempotência vem antes e recusa.
    """
    tornar_amigos(cena.ana, cena.carla)
    chave = _nova_chave()
    ana = _logado(cena.ana)
    primeira = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.b1]), chave)

    outro = _criar(ana, _corpo("carla_03", [cena.a1], [cena.b1]), chave)

    assert primeira.status_code == 201
    assert outro.status_code == 422
    assert outro.json()["code"] == "idempotency_key_reused"
    assert outro.json() != primeira.json()  # não é um replay do 201
    assert TradeOffer.objects.count() == 1
    assert TradeOffer.objects.get().recipient_id == cena.bruno.pk
    assert IdempotencyRecord.objects.count() == 1


def test_a_mesma_chave_em_outra_oferta_ou_outra_acao_da_422(cena: SimpleNamespace) -> None:
    primeira = _a1_por_b1(cena)
    segunda = _criada(_logado(cena.bruno), _corpo("ana_01", [cena.b2], [cena.a2]))
    chave = _nova_chave()
    bruno = _logado(cena.bruno)
    assert _agir(bruno, primeira["id"], "decline", chave).status_code == 200

    outra_oferta = _agir(bruno, segunda["id"], "decline", chave)
    outra_acao = _agir(bruno, primeira["id"], "accept", chave)

    assert outra_oferta.status_code == outra_acao.status_code == 422
    assert outra_oferta.json()["code"] == "idempotency_key_reused"
    assert TradeOffer.objects.get(pk=segunda["id"]).status == "pending"


def test_repetir_o_aceite_com_a_mesma_chave_troca_uma_vez_e_devolve_o_mesmo_corpo(
    cena: SimpleNamespace,
) -> None:
    oferta = _a1_por_b1(cena)
    chave = _nova_chave()
    bruno = _logado(cena.bruno)

    primeira = _agir(bruno, oferta["id"], "accept", chave)
    segunda = _agir(bruno, oferta["id"], "accept", chave)

    assert (primeira.status_code, segunda.status_code) == (200, 200)
    assert segunda.json() == primeira.json()
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.bruno.pk, cena.ana.pk)


def test_a_resposta_repetida_e_o_corpo_gravado_no_primeiro_pedido(cena: SimpleNamespace) -> None:
    """Snapshot: depois de cancelada, repetir a criação ainda devolve a oferta como `pending`."""
    chave = _nova_chave()
    ana = _logado(cena.ana)
    corpo = _corpo("bruno_02", [cena.a1], [cena.b1])
    primeira = _criar(ana, corpo, chave).json()
    assert _agir(ana, primeira["id"], "cancel").status_code == 200

    repetida = _criar(ana, corpo, chave)

    assert repetida.status_code == 201
    assert repetida.json() == primeira
    assert repetida.json()["status"] == "pending"
    assert TradeOffer.objects.get(pk=primeira["id"]).status == "cancelled"
    assert TradeOffer.objects.count() == 1


_ACAO_E_QUEM_AGE = [("accept", "bruno"), ("decline", "bruno"), ("cancel", "ana")]
_CHAVES_INVALIDAS = [
    pytest.param(None, id="ausente"),
    pytest.param("", id="vazia"),
    pytest.param("abc", id="texto"),
    pytest.param("12345", id="numero"),
    pytest.param("7c0f8e1a-0000-4000-8000-00000000000g", id="uuid-com-letra-invalida"),
    pytest.param("a" * 300, id="gigante"),
]


@pytest.mark.parametrize("chave", _CHAVES_INVALIDAS)
def test_criar_sem_chave_valida_da_400_e_nao_cria_nada(
    cena: SimpleNamespace, chave: str | None
) -> None:
    corpo = _corpo("bruno_02", [cena.a1], [cena.b1])

    resposta = _post(_logado(cena.ana), TRADES_URL, corpo, chave)

    assert resposta.status_code == 400
    assert set(resposta.json()) == {"code", "message"}
    assert resposta.json()["code"] == "invalid_idempotency_key"
    assert TradeOffer.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


@pytest.mark.parametrize(("acao", "quem"), _ACAO_E_QUEM_AGE)
@pytest.mark.parametrize("chave", _CHAVES_INVALIDAS)
def test_resolver_sem_chave_valida_da_400_e_a_oferta_continua_pendente(
    cena: SimpleNamespace, acao: str, quem: str, chave: str | None
) -> None:
    oferta = _a1_por_b1(cena)

    resposta = _post(_logado(getattr(cena, quem)), _url(oferta["id"], acao), {}, chave)

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "invalid_idempotency_key"
    assert TradeOffer.objects.get(pk=oferta["id"]).status == "pending"
    assert IdempotencyRecord.objects.count() == 1  # só a da criação
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)


def test_falha_de_negocio_nao_queima_a_chave(cena: SimpleNamespace) -> None:
    chave = _nova_chave()
    ana = _logado(cena.ana)

    errada = _criar(ana, _corpo("bruno_02", [cena.c1], [cena.b1]), chave)  # c1 é da carla
    certa = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.b1]), chave)

    assert errada.status_code == 409
    assert errada.json()["code"] == "item_not_owned"
    assert IdempotencyRecord.objects.count() == 1  # só a do pedido que deu certo
    assert certa.status_code == 201
    assert TradeOffer.objects.count() == 1


def test_resolver_com_erro_de_negocio_tambem_nao_queima_a_chave(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    chave = _nova_chave()
    bruno = _logado(cena.bruno)

    cancelar = _agir(bruno, oferta["id"], "cancel", chave)  # cancelar é do proponente
    recusar = _agir(bruno, oferta["id"], "decline", chave)  # outro pedido, mesma chave

    assert cancelar.status_code == 403
    assert recusar.status_code == 200  # com a chave queimada seria 422
    assert IdempotencyRecord.objects.count() == 2  # a criação e a recusa


def test_a_chave_de_um_usuario_nao_colide_com_a_de_outro(cena: SimpleNamespace) -> None:
    chave = _nova_chave()

    de_ana = _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b1]), chave)
    de_bruno = _criar(_logado(cena.bruno), _corpo("ana_01", [cena.b2], [cena.a2]), chave)

    assert (de_ana.status_code, de_bruno.status_code) == (201, 201)
    assert de_ana.json()["id"] != de_bruno.json()["id"]
    assert TradeOffer.objects.count() == 2
    assert set(IdempotencyRecord.objects.values_list("scope", flat=True)) == {
        f"user:{cena.ana.pk}",
        f"user:{cena.bruno.pk}",
    }


# --- item travado por outro módulo (`inventory.ItemLocked`) ----------------------------------


def _aceite_que_levanta(monkeypatch: Any, erro: Exception) -> None:
    """Substitui o aceite por um que levanta `erro` antes de tocar o banco.

    A view guarda os serviços em `_RESOLVEDORES` no import: trocar só
    `services.accept_offer` não chegaria à rota, então trocamos a entrada da tabela que o
    `AcceptOfferView` de fato chama.
    """

    def falhar(ator: Any, offer_id: Any) -> Any:
        raise erro

    monkeypatch.setitem(views._RESOLVEDORES, "accept", falhar)


def test_item_travado_no_aceite_da_409_item_locked_e_nao_queima_a_chave(
    cena: SimpleNamespace, monkeypatch: Any
) -> None:
    """`ItemLocked` é erro de negócio de outro módulo: 409 `item_locked`, nunca 500."""
    oferta = _a1_por_b1(cena)
    _aceite_que_levanta(monkeypatch, ItemLocked("travado por uma oferta pendente"))

    resposta = _agir(_logado(cena.bruno), oferta["id"], "accept")

    assert resposta.status_code == 409
    assert resposta.json() == {
        "code": "item_locked",
        "message": "travado por uma oferta pendente",
    }
    # o aceite não aconteceu e a transação desfez a chave: o dono não mudou e ela ainda serve
    assert TradeOffer.objects.get(pk=oferta["id"]).status == "pending"
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)
    assert IdempotencyRecord.objects.count() == 1  # só a da criação


def test_trade_error_comum_continua_com_o_status_do_mapa(
    cena: SimpleNamespace, monkeypatch: Any
) -> None:
    """O tratamento novo não engole os `TradeError`: `NotAllowed` continua 403, não 409."""
    oferta = _a1_por_b1(cena)
    _aceite_que_levanta(monkeypatch, services.NotAllowed())

    resposta = _agir(_logado(cena.bruno), oferta["id"], "accept")

    assert resposta.status_code == 403
    assert resposta.json()["code"] == "not_allowed"
    assert TradeOffer.objects.get(pk=oferta["id"]).status == "pending"


def _largar(tarefas: Sequence[Callable[[], Any]]) -> list[Any]:
    """Roda cada tarefa numa thread, soltas juntas por uma barreira; devolve os resultados.

    A conexão abre antes da barreira, para só a transação disputar.
    """
    largada = threading.Barrier(len(tarefas), timeout=ESPERA_MAXIMA_S)

    def rodar(tarefa: Callable[[], Any]) -> Any:
        try:
            connection.ensure_connection()
            largada.wait()
            return tarefa()
        finally:
            connection.close()

    with ThreadPoolExecutor(len(tarefas)) as pool:
        futuros = [pool.submit(rodar, t) for t in tarefas]
        return [f.result(timeout=ESPERA_MAXIMA_S) for f in futuros]


@pytest.mark.django_db(transaction=True)
def test_criar_com_a_mesma_chave_em_paralelo_cria_uma_oferta_so(cena: SimpleNamespace) -> None:
    chave = _nova_chave()
    corpo = _corpo("bruno_02", [cena.a1], [cena.b1])

    resultados = _largar(
        [lambda: _resumo(_criar(_logado(cena.ana), corpo, chave)) for _ in range(N)]
    )

    assert {status for status, _ in resultados} == {201}
    assert len({json.dumps(corpo_, sort_keys=True) for _, corpo_ in resultados}) == 1
    assert TradeOffer.objects.count() == 1
    assert TradeOfferItem.objects.count() == 2
    assert IdempotencyRecord.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_aceitar_com_a_mesma_chave_em_paralelo_troca_uma_vez_so(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    chave = _nova_chave()

    resultados = _largar(
        [lambda: _resumo(_agir(_logado(cena.bruno), oferta["id"], "accept", chave))] * N
    )

    assert {status for status, _ in resultados} == {200}
    assert len({json.dumps(corpo, sort_keys=True) for _, corpo in resultados}) == 1
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.bruno.pk, cena.ana.pk)
    assert IdempotencyRecord.objects.count() == 2  # a criação e o aceite


# --- segurança: quem não faz parte, quem não pode agir ---------------------------------------


def test_terceiro_recebe_404_igual_ao_de_oferta_inexistente(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    carla = _logado(cena.carla)

    de_verdade = {
        "get": carla.get(_url(oferta["id"])),
        "accept": _agir(carla, oferta["id"], "accept"),
        "decline": _agir(carla, oferta["id"], "decline"),
        "cancel": _agir(carla, oferta["id"], "cancel"),
    }
    sem_oferta = {
        "get": carla.get(_url(UM_ID_QUALQUER)),
        "accept": _agir(carla, UM_ID_QUALQUER, "accept"),
        "decline": _agir(carla, UM_ID_QUALQUER, "decline"),
        "cancel": _agir(carla, UM_ID_QUALQUER, "cancel"),
    }

    for rota, resposta in de_verdade.items():
        assert resposta.status_code == 404, rota
        assert resposta.json() == sem_oferta[rota].json(), rota
        assert sem_oferta[rota].status_code == 404, rota
    assert TradeOffer.objects.get(pk=oferta["id"]).status == "pending"
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)


def test_proponente_nao_aceita_nem_recusa_a_propria_oferta(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    ana = _logado(cena.ana)

    aceitar = _agir(ana, oferta["id"], "accept")
    recusar = _agir(ana, oferta["id"], "decline")

    assert (aceitar.status_code, recusar.status_code) == (403, 403)
    assert aceitar.json()["code"] == "not_allowed"
    assert TradeOffer.objects.get(pk=oferta["id"]).status == "pending"
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)


def test_destinatario_nao_cancela_a_oferta_que_recebeu(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)

    resposta = _agir(_logado(cena.bruno), oferta["id"], "cancel")

    assert resposta.status_code == 403
    assert resposta.json()["code"] == "not_allowed"
    assert TradeOffer.objects.get(pk=oferta["id"]).status == "pending"


@pytest.mark.parametrize(
    "variante",
    [
        pytest.param("normal", id="itens-validos"),
        pytest.param("lado-vazio", id="lado-vazio"),
        pytest.param("repetido", id="item-repetido"),
    ],
)
def test_destinatario_inexistente_e_nao_amigo_dao_a_mesma_resposta(
    cena: SimpleNamespace, variante: str
) -> None:
    ana = _logado(cena.ana)
    oferecidos, pedidos = {
        "normal": ([cena.a1], [cena.b1]),
        "lado-vazio": ([], [cena.b1]),
        "repetido": ([cena.a1, cena.a1], [cena.b1]),
    }[variante]

    nao_amiga = _criar(ana, _corpo("carla_03", oferecidos, pedidos))
    inexistente = _criar(ana, _corpo("ninguem_99", oferecidos, pedidos))

    assert nao_amiga.status_code == inexistente.status_code
    assert nao_amiga.json() == inexistente.json()
    if variante == "normal":
        assert (nao_amiga.status_code, nao_amiga.json()["code"]) == (409, "not_friends")
    assert TradeOffer.objects.count() == 0


def test_destinatario_que_me_bloqueou_tambem_da_not_friends(cena: SimpleNamespace) -> None:
    # a linha de bloqueio guarda o bloqueador em `requester`: agora é o bruno quem bloqueou
    Friendship.objects.update(requester=cena.bruno, addressee=cena.ana, status="blocked")
    ana = _logado(cena.ana)

    bloqueado = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.b1]))
    inexistente = _criar(ana, _corpo("ninguem_99", [cena.a1], [cena.b1]))

    assert bloqueado.status_code == inexistente.status_code == 409
    assert bloqueado.json() == inexistente.json()


@pytest.mark.parametrize("nome", ["ana_01", "ANA_01", " ana_01 "])
def test_trocar_consigo_mesmo_da_400_self_trade(cena: SimpleNamespace, nome: str) -> None:
    resposta = _criar(_logado(cena.ana), _corpo(nome, [cena.a1], [cena.a2]))

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "self_trade"
    assert TradeOffer.objects.count() == 0


def test_id_de_item_alheio_ou_inexistente_da_o_mesmo_409_item_not_owned(
    cena: SimpleNamespace,
) -> None:
    ana = _logado(cena.ana)
    casos = {
        "da-carla": _criar(ana, _corpo("bruno_02", [cena.c1], [cena.b1])),
        "do-bruno-no-lado-dela": _criar(ana, _corpo("bruno_02", [cena.b2], [cena.b1])),
        "dela-no-lado-dele": _criar(ana, _corpo("bruno_02", [cena.a1], [cena.a2])),
        "inexistente": _criar(
            ana,
            {
                "recipient": "bruno_02",
                "offered": [UM_ID_QUALQUER],
                "requested": [str(cena.b1.pk)],
            },
        ),
    }

    assert {n: r.status_code for n, r in casos.items()} == dict.fromkeys(casos, 409)
    assert len({json.dumps(r.json(), sort_keys=True) for r in casos.values()}) == 1
    assert next(iter(casos.values())).json()["code"] == "item_not_owned"
    assert TradeOffer.objects.count() == 0


def test_item_consumido_da_409_item_consumed(cena: SimpleNamespace) -> None:
    SkinInstance.objects.filter(pk=cena.b1.pk).update(consumed_at=timezone.now())

    resposta = _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b1]))

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "item_consumed"


def test_item_em_outra_oferta_pendente_da_409_item_already_offered(
    cena: SimpleNamespace,
) -> None:
    _a1_por_b1(cena)

    resposta = _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b2]))

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "item_already_offered"
    assert TradeOffer.objects.count() == 1


def test_o_teto_de_ofertas_pendentes_da_409(cena: SimpleNamespace) -> None:
    ana = _logado(cena.ana)
    for i in range(rules.MAX_PENDING_PER_PROPOSER):
        dela = criar_instancia(cena.ana, criar_skin(f"pa-{i}"))
        dele = criar_instancia(cena.bruno, criar_skin(f"pb-{i}"))
        _criada(ana, _corpo("bruno_02", [dela], [dele]))

    resposta = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.b1]))

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "too_many_pending_offers"


def test_item_repetido_e_lado_vazio_da_400_com_o_codigo_do_servico(cena: SimpleNamespace) -> None:
    ana = _logado(cena.ana)

    repetido = _criar(ana, _corpo("bruno_02", [cena.a1, cena.a1], [cena.b1]))
    entre_lados = _criar(ana, _corpo("bruno_02", [cena.a1], [cena.a1]))
    vazio = _criar(ana, _corpo("bruno_02", [], [cena.b1]))

    assert [r.status_code for r in (repetido, entre_lados, vazio)] == [400, 400, 400]
    assert [r.json()["code"] for r in (repetido, entre_lados, vazio)] == [
        "duplicate_item",
        "duplicate_item",
        "empty_side",
    ]


# --- entrada malformada: nada chega ao banco --------------------------------------------------

_UM_ITEM = str(uuid.UUID(int=7))


_VALIDO: dict[str, Any] = {"recipient": "bruno_02", "offered": [_UM_ITEM], "requested": [_UM_ITEM]}


def _com(**mudancas: Any) -> dict[str, Any]:
    """O corpo válido (ids desconhecidos, que o serviço recusaria) com os campos trocados."""
    return {**_VALIDO, **mudancas}


def _sem(campo: str) -> dict[str, Any]:
    return {k: v for k, v in _VALIDO.items() if k != campo}


def _caso(nome: str, corpo: Any, codigo: str) -> Any:
    return pytest.param(corpo, codigo, id=nome)


@pytest.mark.parametrize(
    ("corpo", "codigo"),
    [
        _caso("corpo-lista", [], "invalid_body"),
        _caso("corpo-texto", "texto", "invalid_body"),
        _caso("corpo-numero", 42, "invalid_body"),
        _caso("campo-extra", _com(price=1), "invalid_body"),
        _caso("objeto-vazio", {}, "invalid_recipient"),
        _caso("sem-recipient", _sem("recipient"), "invalid_recipient"),
        _caso("recipient-numero", _com(recipient=5), "invalid_recipient"),
        _caso("recipient-nulo", _com(recipient=None), "invalid_recipient"),
        _caso("recipient-lista", _com(recipient=["bruno_02"]), "invalid_recipient"),
        _caso("recipient-vazio", _com(recipient=""), "invalid_recipient"),
        _caso("recipient-so-espaco", _com(recipient="   "), "invalid_recipient"),
        _caso("recipient-longo", _com(recipient="x" * 21), "invalid_recipient"),
        _caso("recipient-nul", _com(recipient="bru\x00no"), "invalid_recipient"),
        _caso("sem-offered", _sem("offered"), "invalid_items"),
        _caso("sem-requested", _sem("requested"), "invalid_items"),
        _caso("offered-texto", _com(offered="abc"), "invalid_items"),
        _caso("offered-objeto", _com(offered={"a": 1}), "invalid_items"),
        _caso("requested-nulo", _com(requested=None), "invalid_items"),
        _caso("offered-nao-uuid", _com(offered=["nao-e-uuid"]), "invalid_item_id"),
        _caso("requested-um-ruim", _com(requested=[_UM_ITEM, "x"]), "invalid_item_id"),
        _caso("offered-numero", _com(offered=[1]), "invalid_item_id"),
        _caso("offered-nulo", _com(offered=[None]), "invalid_item_id"),
        _caso("offered-aninhada", _com(offered=[[_UM_ITEM]]), "invalid_item_id"),
        _caso("offered-objeto-item", _com(offered=[{"id": _UM_ITEM}]), "invalid_item_id"),
        _caso(
            "21-itens-no-lado",
            _com(offered=[str(uuid.UUID(int=i)) for i in range(1, 22)]),
            "too_many_items",
        ),
        _caso(
            "lista-gigante",
            _com(requested=[str(uuid.uuid4()) for _ in range(5000)]),
            "too_many_items",
        ),
    ],
)
def test_corpo_malformado_da_400_sem_tocar_o_banco(
    cena: SimpleNamespace, django_assert_num_queries: Any, corpo: Any, codigo: str
) -> None:
    with django_assert_num_queries(0):
        resposta = _criar(_logado(cena.ana), corpo)

    assert resposta.status_code == 400
    assert set(resposta.json()) == {"code", "message"}
    assert resposta.json()["code"] == codigo
    assert TradeOffer.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


def test_json_quebrado_da_400(cena: SimpleNamespace) -> None:
    resposta = _logado(cena.ana).post(
        TRADES_URL,
        "{nao e json",
        content_type="application/json",
        headers={CABECALHO: _nova_chave()},
    )

    assert resposta.status_code == 400
    assert TradeOffer.objects.count() == 0


@pytest.mark.parametrize("extra", ["price", "proposer", "status", "id", "active"])
def test_campo_desconhecido_no_corpo_da_400_e_nao_cria_nada(
    cena: SimpleNamespace, extra: str
) -> None:
    """Corpo VÁLIDO (itens de verdade, amigo de verdade) mais um campo que a API não define."""
    corpo = {**_corpo("bruno_02", [cena.a1], [cena.b1]), extra: "qualquer"}

    resposta = _criar(_logado(cena.ana), corpo)

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "invalid_body"
    assert TradeOffer.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0
    # sem o campo extra, o mesmo corpo passa: era ele o motivo da recusa
    assert _criar(_logado(cena.ana), _corpo("bruno_02", [cena.a1], [cena.b1])).status_code == 201


def test_o_teto_de_20_por_lado_passa_da_view_e_cai_no_servico(cena: SimpleNamespace) -> None:
    """Exatamente 20 ids desconhecidos: a view deixa passar e o serviço diz que não são dela."""
    # fora de `_UM_ITEM` (int=7), que está do outro lado: um repetido daria 400 `duplicate_item`
    desconhecidos = [str(uuid.UUID(int=i)) for i in range(100, 100 + rules.MAX_ITEMS_PER_SIDE)]

    resposta = _criar(_logado(cena.ana), _com(offered=desconhecidos, requested=[_UM_ITEM]))

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "item_not_owned"


# --- leitura --------------------------------------------------------------------------------


def test_listar_devolve_so_as_ofertas_de_que_o_usuario_faz_parte_mais_novas_primeiro(
    cena: SimpleNamespace,
) -> None:
    primeira = _a1_por_b1(cena)
    segunda = _criada(_logado(cena.bruno), _corpo("ana_01", [cena.b2], [cena.a2]))
    assert _agir(_logado(cena.ana), primeira["id"], "cancel").status_code == 200
    terceira = _a1_por_b1(cena)  # as mesmas instâncias, de novo

    da_ana = _logado(cena.ana).get(TRADES_URL)
    do_bruno = _logado(cena.bruno).get(TRADES_URL)
    da_carla = _logado(cena.carla).get(TRADES_URL)

    assert da_ana.status_code == do_bruno.status_code == da_carla.status_code == 200
    esperados = [terceira["id"], segunda["id"], primeira["id"]]
    assert [o["id"] for o in da_ana.json()["results"]] == esperados
    assert [o["id"] for o in do_bruno.json()["results"]] == esperados
    assert [o["status"] for o in da_ana.json()["results"]] == ["pending", "pending", "cancelled"]
    assert da_ana.json()["count"] == 3
    assert da_carla.json()["count"] == 0
    assert da_carla.json()["results"] == []


def test_a_lista_e_paginada_e_page_size_invalido_ou_alto_e_ajustado_em_silencio(
    cena: SimpleNamespace,
) -> None:
    """Diferente do inventário (que dá 400 para `page_size` inválido ou acima do teto), a lista
    de trocas não valida: `page_size` fora da regra vira o padrão (20) ou o teto (100), sem erro.
    O teto de 100 não é provado aqui (o limite de pendentes impede criar 100 ofertas)."""
    primeira = _a1_por_b1(cena)
    _criada(_logado(cena.bruno), _corpo("ana_01", [cena.b2], [cena.a2]))
    assert _agir(_logado(cena.ana), primeira["id"], "cancel").status_code == 200
    _a1_por_b1(cena)
    ana = _logado(cena.ana)

    pagina_1 = ana.get(TRADES_URL, {"page_size": "2"}).json()
    pagina_2 = ana.get(TRADES_URL, {"page_size": "2", "page": "2"}).json()

    assert (pagina_1["count"], len(pagina_1["results"])) == (3, 2)
    assert pagina_1["next"] is not None
    assert len(pagina_2["results"]) == 1
    assert pagina_2["results"][0]["id"] == primeira["id"]  # a mais antiga fecha a lista
    for ajustado in ("100000", "abc", "0", "-1"):
        resposta = ana.get(TRADES_URL, {"page_size": ajustado})
        assert resposta.status_code == 200, ajustado
        assert len(resposta.json()["results"]) == 3, ajustado


def test_detalhe_mostra_a_oferta_para_os_dois_lados(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)

    da_ana = _logado(cena.ana).get(_url(oferta["id"]))
    do_bruno = _logado(cena.bruno).get(_url(oferta["id"]))

    assert (da_ana.status_code, do_bruno.status_code) == (200, 200)
    assert da_ana.json() == do_bruno.json() == oferta


def test_o_detalhe_reflete_o_estado_atual_e_nao_o_do_primeiro_pedido(
    cena: SimpleNamespace,
) -> None:
    oferta = _a1_por_b1(cena)
    assert _agir(_logado(cena.bruno), oferta["id"], "accept").status_code == 200

    resposta = _logado(cena.ana).get(_url(oferta["id"]))

    assert resposta.json()["status"] == "accepted"
    assert resposta.json()["resolved_at"] is not None


def _consultas(cliente: APIClient, url: str) -> int:
    with CaptureQueriesContext(connection) as contexto:
        assert cliente.get(url).status_code == 200
    return len(contexto)


def test_o_numero_de_queries_da_lista_nao_cresce_com_o_numero_de_ofertas(
    cena: SimpleNamespace,
) -> None:
    ana = _logado(cena.ana)
    _a1_por_b1(cena)
    com_uma = _consultas(ana, TRADES_URL)

    for i in range(5):
        dela = criar_instancia(cena.ana, criar_skin(f"la-{i}"))
        dele = criar_instancia(cena.bruno, criar_skin(f"lb-{i}"))
        _criada(ana, _corpo("bruno_02", [dela], [dele]))

    assert _consultas(ana, TRADES_URL) == com_uma


def test_o_numero_de_queries_do_detalhe_nao_cresce_com_o_numero_de_itens(
    cena: SimpleNamespace,
) -> None:
    ana = _logado(cena.ana)
    pequena = _a1_por_b1(cena)
    com_dois_itens = _consultas(ana, _url(pequena["id"]))
    dela = [criar_instancia(cena.ana, criar_skin(f"da-{i}")) for i in range(4)]
    dele = [criar_instancia(cena.bruno, criar_skin(f"db-{i}")) for i in range(4)]
    grande = _criada(ana, _corpo("bruno_02", dela, dele))

    assert len(grande["items"]) == 8
    assert _consultas(ana, _url(grande["id"])) == com_dois_itens


# --- anti-enumeração: o custo também é igual -----------------------------------------------


def _consultas_do_post(cliente: APIClient, corpo: Any) -> tuple[int, list[str]]:
    with CaptureQueriesContext(connection) as contexto:
        resposta = _criar(cliente, corpo)
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "not_friends"
    return len(contexto), [q["sql"] for q in contexto.captured_queries]


def test_destinatario_inexistente_e_nao_amigo_fazem_o_mesmo_numero_de_consultas(
    cena: SimpleNamespace,
) -> None:
    ana = _logado(cena.ana)
    corpo_nao_amiga = _corpo("carla_03", [cena.a1], [cena.b1])
    corpo_inexistente = _corpo("ninguem_99", [cena.a1], [cena.b1])

    n_nao_amiga, sql_nao_amiga = _consultas_do_post(ana, corpo_nao_amiga)
    n_inexistente, sql_inexistente = _consultas_do_post(ana, corpo_inexistente)

    detalhe = "\n".join(["nao amiga:", *sql_nao_amiga, "inexistente:", *sql_inexistente])
    assert n_nao_amiga == n_inexistente, detalhe


# --- toda classe de erro do serviço tem status ----------------------------------------------


def _sem_status(raiz: type, mapa: Mapping[Any, int]) -> list[str]:
    """Os nomes das subclasses (em qualquer profundidade) de `raiz` que `mapa` não conhece."""
    achados: list[str] = []
    pendentes: list[type] = list(raiz.__subclasses__())
    while pendentes:
        classe = pendentes.pop()
        pendentes.extend(classe.__subclasses__())
        if classe not in mapa:
            achados.append(classe.__name__)
    return sorted(achados)


def test_toda_subclasse_de_trade_error_tem_status_na_view() -> None:
    assert _sem_status(services.TradeError, views._STATUS_DO_ERRO) == []
    assert services.TradeError not in views._STATUS_DO_ERRO  # a base não é um erro "de verdade"
    assert set(views._STATUS_DO_ERRO.values()) <= {400, 403, 404, 409}


def test_o_helper_acusa_uma_subclasse_nova_sem_status() -> None:
    """Prova de que o teste acima cairia. Raiz LOCAL: não polui `TradeError.__subclasses__`."""

    class Raiz(Exception):
        pass

    class Mapeada(Raiz):
        pass

    class Neta(Mapeada):  # profundidade 2: `__subclasses__` direto não a veria
        pass

    assert _sem_status(Raiz, {Mapeada: 400}) == ["Neta"]
    assert _sem_status(Raiz, {Mapeada: 400, Neta: 409}) == []


# --- CSRF: a API é de sessão, e o POST sem token tem de ser recusado -----------------------

CONFIG_DO_ALLAUTH = "/_allauth/browser/v1/config"
_POSTS = [("create", 201), ("accept", 200), ("decline", 200), ("cancel", 200)]


def _post_de(cena: SimpleNamespace, acao: str) -> tuple[str, Any, Any]:
    """A URL, o corpo e quem faz cada um dos quatro POST (a oferta, se precisa, já existe)."""
    if acao == "create":
        return TRADES_URL, _corpo("bruno_02", [cena.a1], [cena.b1]), cena.ana
    oferta = _a1_por_b1(cena)
    return _url(oferta["id"], acao), {}, cena.ana if acao == "cancel" else cena.bruno


def _navegador(usuario: Any) -> tuple[APIClient, str]:
    """Cliente que EXIGE CSRF e entra por sessão (`force_authenticate` pularia a checagem)."""
    cliente = APIClient(enforce_csrf_checks=True)
    cliente.force_login(usuario)
    cliente.get(CONFIG_DO_ALLAUTH)  # o servidor entrega o cookie `csrftoken`, como ao frontend
    return cliente, cliente.cookies["csrftoken"].value


def _estado() -> tuple[int, int]:
    return TradeOffer.objects.filter(status="pending").count(), IdempotencyRecord.objects.count()


@pytest.mark.parametrize("acao", [a for a, _ in _POSTS])
def test_post_sem_token_csrf_e_recusado_e_nada_muda(cena: SimpleNamespace, acao: str) -> None:
    url, corpo, quem = _post_de(cena, acao)
    cliente, _ = _navegador(quem)
    antes = _estado()

    resposta = _post(cliente, url, corpo, _nova_chave())

    assert resposta.status_code == 403
    assert _estado() == antes
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)


@pytest.mark.parametrize(("acao", "esperado"), _POSTS)
def test_post_com_token_csrf_passa(cena: SimpleNamespace, acao: str, esperado: int) -> None:
    url, corpo, quem = _post_de(cena, acao)
    cliente, token = _navegador(quem)
    cabecalhos = {CABECALHO: _nova_chave(), "X-CSRFToken": token}

    resposta = cliente.post(url, corpo, format="json", headers=cabecalhos)

    assert resposta.status_code == esperado, resposta.content
