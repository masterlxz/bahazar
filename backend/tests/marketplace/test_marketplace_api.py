"""API do mercado de anúncios: criar, cancelar, listar e ler.

Cena (conftest): ana vende; bruno é amigo dela; carla tem c1, que é de outra pessoa. ana tem a1
(float 0,123456789) e a2; bruno tem b1 e b2. O anúncio expõe só o que a vitrine precisa: o item
continua com o vendedor, e o preço é inteiro em centavos.
"""

import uuid
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import SkinInstance
from apps.marketplace import services, views
from apps.marketplace.models import MarketListing
from apps.trades import services as trades_services

from .conftest import LISTINGS_URL, criar_instancia, criar_skin, logado, nova_chave

UM_ID_QUALQUER = "7c0f8e1a-0000-4000-8000-000000000001"
CONFIG_DO_ALLAUTH = "/_allauth/browser/v1/config"

pytestmark = pytest.mark.django_db


def _url(listing_id: Any, acao: str = "") -> str:
    return f"{LISTINGS_URL}{listing_id}/{acao}/" if acao else f"{LISTINGS_URL}{listing_id}/"


def _criar(cliente: APIClient, instancia: Any, price: Any = 1000, chave: str | None = None) -> Any:
    """POST de criar; sem `chave`, cada chamada é uma intenção nova (chave nova)."""
    return cliente.post(
        LISTINGS_URL,
        {"instance_id": str(instancia.pk), "price": price},
        format="json",
        HTTP_IDEMPOTENCY_KEY=chave or nova_chave(),
    )


def _criada(cliente: APIClient, instancia: Any, price: Any = 1000) -> dict[str, Any]:
    resposta = _criar(cliente, instancia, price)
    assert resposta.status_code == 201, resposta.content
    dados: dict[str, Any] = resposta.json()
    return dados


def _cancelar(cliente: APIClient, listing_id: Any, chave: str | None = None) -> Any:
    """POST de cancelar; sem `chave`, cada chamada é uma intenção nova (chave nova)."""
    return cliente.post(
        _url(listing_id, "cancel"), {}, format="json", HTTP_IDEMPOTENCY_KEY=chave or nova_chave()
    )


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


# --- autenticação e contrato de métodos ------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "url"),
    [
        ("GET", LISTINGS_URL),
        ("POST", LISTINGS_URL),
        ("GET", _url(UM_ID_QUALQUER)),
        ("POST", _url(UM_ID_QUALQUER, "cancel")),
    ],
)
def test_anonimo_nao_acessa_nenhuma_rota(metodo: str, url: str) -> None:
    resposta = APIClient().generic(metodo, url)

    assert resposta.status_code in (401, 403)


@pytest.mark.parametrize(
    ("metodo", "url"),
    [
        ("DELETE", LISTINGS_URL),
        ("PUT", LISTINGS_URL),
        ("DELETE", _url(UM_ID_QUALQUER)),
        ("POST", _url(UM_ID_QUALQUER)),
        ("GET", _url(UM_ID_QUALQUER, "cancel")),
    ],
)
def test_metodos_fora_do_contrato_sao_recusados(
    cena: SimpleNamespace, metodo: str, url: str
) -> None:
    resposta = logado(cena.ana).generic(metodo, url)

    assert resposta.status_code == 405


# --- criar ------------------------------------------------------------------------------------


def test_criar_devolve_201_com_o_anuncio_e_o_item_continua_do_vendedor(
    cena: SimpleNamespace,
) -> None:
    resposta = _criar(logado(cena.ana), cena.a1, price=1234)

    assert resposta.status_code == 201, resposta.content
    anuncio = resposta.json()
    assert anuncio["price"] == 1234
    assert anuncio["status"] == "active"
    assert anuncio["closed_at"] is None
    assert anuncio["seller"] == {"id": str(cena.ana.pk), "username": "ana_01"}
    assert anuncio["instance"]["id"] == str(cena.a1.pk)
    assert anuncio["instance"]["float_value"] == "0.123456789"
    assert anuncio["instance"]["skin"] == {
        "id": str(cena.skin.pk),
        "name": cena.skin.name,
        "weapon": "AK-47",
        "rarity": "Classified",
    }
    assert MarketListing.objects.filter(pk=anuncio["id"], status="active", price=1234).count() == 1
    # o anúncio não move o item: quem move dono é `inventory.services.change_owner`
    assert _dono(cena.a1) == cena.ana.pk
    assert SkinInstance.objects.get(pk=cena.a1.pk).float_value == cena.a1.float_value


def test_o_corpo_do_anuncio_tem_so_os_campos_publicos(cena: SimpleNamespace) -> None:
    resposta = _criar(logado(cena.ana), cena.a1)

    anuncio = resposta.json()
    assert set(anuncio) == {
        "id",
        "price",
        "status",
        "created_at",
        "closed_at",
        "seller",
        "instance",
    }
    assert set(anuncio["seller"]) == {"id", "username"}
    assert set(anuncio["instance"]) == {"id", "float_value", "skin"}
    assert set(anuncio["instance"]["skin"]) == {"id", "name", "weapon", "rarity"}
    internos = {"email", "active", "acquired_via", "consumed_at", "owner", "password"}
    chaves = set(anuncio["seller"]) | set(anuncio["instance"])
    assert chaves.isdisjoint(internos)
    assert "@exemplo.com" not in resposta.content.decode()


def test_o_preco_e_inteiro_em_centavos_e_o_minimo_de_um_centavo_e_aceito(
    cena: SimpleNamespace,
) -> None:
    """Um centavo é o menor preço válido; o corpo da vitrine devolve o inteiro, não um texto."""
    anuncio = _criada(logado(cena.ana), cena.a2, price=1)

    assert anuncio["price"] == 1
    assert MarketListing.objects.get(pk=anuncio["id"]).price == 1


# --- entrada malformada: nada chega ao banco ---------------------------------------------------

_UM_ITEM = str(uuid.UUID(int=7))


def _com(**mudancas: Any) -> dict[str, Any]:
    return {"instance_id": _UM_ITEM, "price": 1000, **mudancas}


def _sem(campo: str) -> dict[str, Any]:
    return {k: v for k, v in _com().items() if k != campo}


def _caso(nome: str, corpo: Any, codigo: str) -> Any:
    return pytest.param(corpo, codigo, id=nome)


@pytest.mark.parametrize(
    ("corpo", "codigo"),
    [
        _caso("corpo-lista", [], "invalid_body"),
        _caso("corpo-texto", "texto", "invalid_body"),
        _caso("corpo-nulo", None, "invalid_body"),
        _caso("campo-extra", _com(seller="ana_01"), "invalid_body"),
        _caso("campo-status", _com(status="active"), "invalid_body"),
        _caso("sem-instance", _sem("instance_id"), "invalid_body"),
        _caso("instance-numero", _com(instance_id=5), "invalid_body"),
        _caso("instance-nulo", _com(instance_id=None), "invalid_body"),
        _caso("instance-vazio", _com(instance_id=""), "invalid_body"),
        _caso("instance-nao-uuid", _com(instance_id="nao-e-uuid"), "invalid_body"),
        _caso("instance-lista", _com(instance_id=[_UM_ITEM]), "invalid_body"),
        _caso("sem-price", _sem("price"), "invalid_price"),
        _caso("price-zero", _com(price=0), "invalid_price"),
        _caso("price-negativo", _com(price=-1), "invalid_price"),
        _caso("price-texto", _com(price="1000"), "invalid_price"),
        _caso("price-float", _com(price=1000.0), "invalid_price"),
        _caso("price-nulo", _com(price=None), "invalid_price"),
        _caso("price-booleano", _com(price=True), "invalid_price"),
        _caso("price-grande-demais", _com(price=2**63), "invalid_price"),
    ],
)
def test_corpo_malformado_da_400_sem_tocar_o_banco(
    cena: SimpleNamespace, django_assert_num_queries: Any, corpo: Any, codigo: str
) -> None:
    with django_assert_num_queries(0):
        resposta = logado(cena.ana).post(LISTINGS_URL, corpo, format="json")

    assert resposta.status_code == 400
    assert set(resposta.json()) == {"code", "message"}
    assert resposta.json()["code"] == codigo
    assert MarketListing.objects.count() == 0


def test_json_quebrado_da_400(cena: SimpleNamespace) -> None:
    resposta = logado(cena.ana).post(LISTINGS_URL, "{nao e json", content_type="application/json")

    assert resposta.status_code == 400
    assert MarketListing.objects.count() == 0


def test_campo_desconhecido_no_corpo_valido_da_400_e_nao_cria_nada(
    cena: SimpleNamespace,
) -> None:
    corpo = {"instance_id": str(cena.a1.pk), "price": 1000, "seller": str(cena.carla.pk)}

    resposta = logado(cena.ana).post(LISTINGS_URL, corpo, format="json")

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "invalid_body"
    assert MarketListing.objects.count() == 0
    # sem o campo extra, o mesmo corpo passa: era ele o motivo da recusa
    assert _criar(logado(cena.ana), cena.a1).status_code == 201


# --- regras de posse e de estado do item -------------------------------------------------------


def test_item_de_outro_dono_da_404_igual_ao_de_item_inexistente(cena: SimpleNamespace) -> None:
    """c1 é da carla: ana não descobre nem que ele existe; b1 é do amigo e também não é dela."""
    ana = logado(cena.ana)
    alheio = _criar(ana, cena.c1)
    do_amigo = _criar(ana, cena.b1)
    inexistente = ana.post(
        LISTINGS_URL,
        {"instance_id": UM_ID_QUALQUER, "price": 1000},
        format="json",
        HTTP_IDEMPOTENCY_KEY=nova_chave(),
    )

    assert (alheio.status_code, do_amigo.status_code, inexistente.status_code) == (404, 404, 404)
    assert alheio.json() == do_amigo.json() == inexistente.json()
    assert inexistente.json() == {"code": "instance_not_found", "message": "Não encontrado."}
    assert MarketListing.objects.count() == 0
    assert (_dono(cena.c1), _dono(cena.b1)) == (cena.carla.pk, cena.bruno.pk)


def test_item_consumido_da_409_e_nao_cria(cena: SimpleNamespace) -> None:
    """O item é da própria ana: só o consumo o impede de ser anunciado."""
    SkinInstance.objects.filter(pk=cena.a1.pk).update(consumed_at=timezone.now())

    resposta = _criar(logado(cena.ana), cena.a1)

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "item_consumed"
    assert MarketListing.objects.count() == 0


def test_o_mesmo_item_nao_ganha_dois_anuncios_ativos(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    primeiro = _criada(ana, cena.a1)

    segunda = _criar(ana, cena.a1, price=999)

    assert segunda.status_code == 409
    assert segunda.json()["code"] == "item_already_listed"
    assert MarketListing.objects.filter(status="active").count() == 1
    assert MarketListing.objects.get(pk=primeiro["id"]).price == 1000


def test_item_em_oferta_pendente_do_trades_da_409_item_locked(cena: SimpleNamespace) -> None:
    """A guarda de `trades` vista de fora: o mercado não anuncia item preso em oferta."""
    trades_services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])

    resposta = _criar(logado(cena.ana), cena.a1)

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "item_locked"
    assert MarketListing.objects.count() == 0
    assert _dono(cena.a1) == cena.ana.pk


# --- cancelar ---------------------------------------------------------------------------------


def test_o_vendedor_cancela_e_o_item_volta_a_ser_anunciado(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    anuncio = _criada(ana, cena.a1)

    resposta = _cancelar(ana, anuncio["id"])

    assert resposta.status_code == 200
    cancelado = resposta.json()
    assert cancelado["status"] == "cancelled"
    assert cancelado["closed_at"] is not None
    assert cancelado["id"] == anuncio["id"]
    gravado = MarketListing.objects.get(pk=anuncio["id"])
    assert (gravado.status, gravado.closed_at is not None) == ("cancelled", True)
    # cancelar não apaga o anúncio nem move o item; só libera o item para outro anúncio
    assert MarketListing.objects.count() == 1
    assert _dono(cena.a1) == cena.ana.pk
    novo = _criar(ana, cena.a1)
    assert novo.status_code == 201
    assert novo.json()["id"] != anuncio["id"]


def test_quem_nao_e_o_vendedor_recebe_404_igual_ao_de_anuncio_inexistente(
    cena: SimpleNamespace,
) -> None:
    anuncio = _criada(logado(cena.ana), cena.a1)
    bruno = logado(cena.bruno)

    de_verdade = _cancelar(bruno, anuncio["id"])
    sem_anuncio = _cancelar(bruno, UM_ID_QUALQUER)

    assert (de_verdade.status_code, sem_anuncio.status_code) == (404, 404)
    assert de_verdade.json() == sem_anuncio.json()
    assert de_verdade.json() == {"code": "listing_not_found", "message": "Não encontrado."}
    assert MarketListing.objects.get(pk=anuncio["id"]).status == "active"


def test_cancelar_duas_vezes_da_409_e_o_primeiro_fechamento_fica(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    anuncio = _criada(ana, cena.a1)
    assert _cancelar(ana, anuncio["id"]).status_code == 200
    fechado = MarketListing.objects.get(pk=anuncio["id"]).closed_at

    segunda = _cancelar(ana, anuncio["id"])

    assert segunda.status_code == 409
    assert segunda.json()["code"] == "listing_not_active"
    gravado = MarketListing.objects.get(pk=anuncio["id"])
    assert gravado.status == "cancelled"
    assert fechado is not None
    assert gravado.closed_at == fechado


# --- listar e ler -----------------------------------------------------------------------------


def test_a_vitrine_so_mostra_ativos_mais_novos_primeiro(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    primeiro = _criada(ana, cena.a1)
    segundo = _criada(ana, cena.a2)
    terceiro = _criada(logado(cena.bruno), cena.b1)
    assert _cancelar(ana, segundo["id"]).status_code == 200

    resposta = ana.get(LISTINGS_URL)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["count"] == 2
    assert [a["id"] for a in corpo["results"]] == [terceiro["id"], primeiro["id"]]
    assert {a["status"] for a in corpo["results"]} == {"active"}
    assert [a["seller"]["username"] for a in corpo["results"]] == ["bruno_02", "ana_01"]


def test_created_at_empatado_desempata_por_id_decrescente(cena: SimpleNamespace) -> None:
    """Sem o desempate, a paginação repete ou pula anúncios criados no mesmo instante."""
    _criada(logado(cena.ana), cena.a1)
    _criada(logado(cena.ana), cena.a2)
    _criada(logado(cena.bruno), cena.b1)
    momento = timezone.now()
    MarketListing.objects.update(created_at=momento)
    esperados = [str(pk) for pk in sorted(MarketListing.objects.values_list("pk", flat=True))]

    resposta = logado(cena.ana).get(LISTINGS_URL)

    assert [a["id"] for a in resposta.json()["results"]] == esperados[::-1]


def test_a_lista_e_paginada_com_count_next_e_previous(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    _criada(ana, cena.a1)
    _criada(ana, cena.a2)
    _criada(logado(cena.bruno), cena.b1)

    primeira = ana.get(LISTINGS_URL, {"page_size": "2"})
    segunda = ana.get(LISTINGS_URL, {"page_size": "2", "page": "2"})

    assert primeira.status_code == segunda.status_code == 200
    pagina_1, pagina_2 = primeira.json(), segunda.json()
    assert pagina_1["count"] == 3
    assert len(pagina_1["results"]) == 2
    assert pagina_1["previous"] is None
    assert pagina_1["next"] is not None
    assert len(pagina_2["results"]) == 1
    assert pagina_2["next"] is None
    assert pagina_2["previous"] is not None
    ids = [a["id"] for a in pagina_1["results"] + pagina_2["results"]]
    assert len(set(ids)) == 3


def test_a_vitrine_e_publica_para_qualquer_autenticado(cena: SimpleNamespace) -> None:
    anuncio = _criada(logado(cena.ana), cena.a1)

    resposta = logado(cena.carla).get(LISTINGS_URL)

    assert resposta.status_code == 200
    assert [a["id"] for a in resposta.json()["results"]] == [anuncio["id"]]


def test_o_detalhe_mostra_so_anuncio_ativo(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    anuncio = _criada(ana, cena.a1)

    ativo = logado(cena.carla).get(_url(anuncio["id"]))
    sem_anuncio = logado(cena.carla).get(_url(UM_ID_QUALQUER))
    assert _cancelar(ana, anuncio["id"]).status_code == 200
    depois = ana.get(_url(anuncio["id"]))

    assert ativo.status_code == 200
    assert ativo.json() == anuncio
    assert (depois.status_code, sem_anuncio.status_code) == (404, 404)
    assert (
        depois.json()
        == sem_anuncio.json()
        == {
            "code": "listing_not_found",
            "message": "Não encontrado.",
        }
    )


def _consultas(cliente: APIClient, url: str) -> int:
    with CaptureQueriesContext(connection) as contexto:
        assert cliente.get(url).status_code == 200
    return len(contexto)


def test_o_numero_de_queries_da_vitrine_nao_cresce_com_o_numero_de_anuncios(
    cena: SimpleNamespace,
) -> None:
    ana = logado(cena.ana)
    _criada(ana, cena.a1)
    com_um = _consultas(ana, LISTINGS_URL)

    for i in range(5):
        _criada(ana, criar_instancia(cena.ana, criar_skin(f"vitrine-{i}")))

    assert _consultas(ana, LISTINGS_URL) == com_um


# --- toda classe de erro do serviço tem status ------------------------------------------------


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


def test_toda_subclasse_de_market_error_tem_status_na_view() -> None:
    assert _sem_status(services.MarketError, views._STATUS_DO_ERRO) == []
    assert services.MarketError not in views._STATUS_DO_ERRO
    # 422: saldo e chave reusada; 503: a idempotência esgotou as tentativas (nada executou)
    assert set(views._STATUS_DO_ERRO.values()) <= {400, 404, 409, 422, 503}


def test_o_helper_acusa_uma_subclasse_nova_sem_status() -> None:
    class Raiz(Exception):
        pass

    class Mapeada(Raiz):
        pass

    class Neta(Mapeada):
        pass

    assert _sem_status(Raiz, {Mapeada: 400}) == ["Neta"]
    assert _sem_status(Raiz, {Mapeada: 400, Neta: 409}) == []


# --- CSRF: a API é de sessão, e o POST sem token tem de ser recusado ---------------------------


def _navegador(usuario: Any) -> tuple[APIClient, str]:
    """Cliente que EXIGE CSRF e entra por sessão (`force_authenticate` pularia a checagem)."""
    cliente = APIClient(enforce_csrf_checks=True)
    cliente.force_login(usuario)
    cliente.get(CONFIG_DO_ALLAUTH)  # o servidor entrega o cookie `csrftoken`, como ao frontend
    return cliente, cliente.cookies["csrftoken"].value


def _posts(cena: SimpleNamespace) -> dict[str, tuple[Any, Any, int]]:
    """(url, corpo, status esperado) de cada POST, com o anúncio já criado se preciso."""
    anuncio = _criada(logado(cena.ana), cena.a1)
    return {
        "criar": (LISTINGS_URL, {"instance_id": str(cena.a2.pk), "price": 500}, 201),
        "cancelar": (_url(anuncio["id"], "cancel"), {}, 200),
    }


@pytest.mark.parametrize("acao", ["criar", "cancelar"])
def test_post_sem_token_csrf_e_recusado_e_nada_muda(cena: SimpleNamespace, acao: str) -> None:
    url, corpo, _ = _posts(cena)[acao]
    cliente, _ = _navegador(cena.ana)
    antes = MarketListing.objects.filter(status="active").count()

    resposta = cliente.post(url, corpo, format="json")

    assert resposta.status_code == 403
    assert MarketListing.objects.filter(status="active").count() == antes


@pytest.mark.parametrize("acao", ["criar", "cancelar"])
def test_post_com_token_csrf_passa(cena: SimpleNamespace, acao: str) -> None:
    url, corpo, esperado = _posts(cena)[acao]
    cliente, token = _navegador(cena.ana)

    resposta = cliente.post(
        url,
        corpo,
        format="json",
        headers={"X-CSRFToken": token, "Idempotency-Key": nova_chave()},
    )

    assert resposta.status_code == esperado, resposta.content
