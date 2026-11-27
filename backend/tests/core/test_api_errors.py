"""Erros do próprio DRF saem como `{code, message}`, por rotas reais (não só pelo handler).

Antes, JSON quebrado, `?page` inválida, 403, 405 e 429 saíam como `{"detail": "..."}` (em inglês
ou traduzido pelo DRF) e o frontend, que lê `ApiError.code`, caía no erro genérico. O corpo agora é
IGUAL a `{"code": ..., "message": ...}`: nada de `detail`, nenhum campo a mais. O status e os
cabeçalhos (`Allow`, `Retry-After`) não mudam.
"""

import re
import uuid
from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from .conftest import (
    CATALOG_URL,
    CONFIG_URL,
    DAILY_URL,
    INVENTORY_URL,
    JOIN_URL,
    ROOMS_URL,
    WALLET_URL,
    com_sessao,
    criar_skin,
    logado,
)

pytestmark = pytest.mark.django_db

PARSE_ERROR = "O corpo da requisição é inválido."
NOT_FOUND = "Não encontrado."
METHOD_NOT_ALLOWED = "Método não permitido."
THROTTLED = "Muitas requisições. Tente novamente em instantes."
PERMISSION_DENIED = "Você não tem permissão para realizar esta ação."
NOT_AUTHENTICATED = "Autenticação necessária."
NOT_ACCEPTABLE = "Formato de resposta não suportado."
UNSUPPORTED_MEDIA_TYPE = "Formato do corpo não suportado."
INVALID_REQUEST = "Requisição inválida."

SALA_QUE_NAO_EXISTE = "00000000-0000-4000-8000-000000000001"


def _confere(resposta: Any, status: int, code: str, message: str) -> None:
    """Status e corpo EXATOS: igualdade de dicionário também barra `detail` e campo a mais."""
    assert resposta.status_code == status
    assert resposta.json() == {"code": code, "message": message}


def _criar_sala(usuario: Any, nome: str = "Amigos") -> dict[str, Any]:
    resposta = logado(usuario).post(ROOMS_URL, {"name": nome}, format="json")
    assert resposta.status_code == 201, resposta.content
    dados: dict[str, Any] = resposta.json()
    return dados


# --- JSON quebrado: 400 parse_error -----------------------------------------------------------


@pytest.mark.parametrize("corpo", ['{"name": ', "isto nao e json", '{"name": "Amigos",}'])
def test_json_quebrado_no_post_da_400_parse_error(ana: Any, corpo: str) -> None:
    from apps.rooms.models import Room

    resposta = logado(ana).post(ROOMS_URL, data=corpo, content_type="application/json")

    _confere(resposta, 400, "parse_error", PARSE_ERROR)
    assert Room.objects.count() == 0


def test_json_quebrado_tambem_vale_para_a_rota_de_entrar_na_sala(bruno: Any) -> None:
    resposta = logado(bruno).post(JOIN_URL, data='{"code": ', content_type="application/json")

    _confere(resposta, 400, "parse_error", PARSE_ERROR)


# --- 404: página inválida e objeto que o usuário não enxerga ----------------------------------


def test_pagina_valida_do_catalogo_continua_200(ana: Any) -> None:
    """Premissa dos testes de página: com UMA skin a página 1 existe e a rota responde 200.

    O catálogo exige login (vale o padrão negar do DRF; o comentário "público" da view não vale).
    """
    criar_skin()

    resposta = logado(ana).get(CATALOG_URL, {"page": 1})

    assert resposta.status_code == 200
    assert len(resposta.json()["results"]) == 1


@pytest.mark.parametrize("pagina", ["2", "999", "0", "abc"])
def test_pagina_invalida_do_catalogo_da_404_not_found(ana: Any, pagina: str) -> None:
    criar_skin()  # uma skin: só a página 1 existe; "2" falha mesmo sendo um número pequeno

    resposta = logado(ana).get(CATALOG_URL, {"page": pagina})

    _confere(resposta, 404, "not_found", NOT_FOUND)


def test_sala_que_nao_existe_da_404_not_found(ana: Any) -> None:
    resposta = logado(ana).get(f"{ROOMS_URL}{SALA_QUE_NAO_EXISTE}/")

    _confere(resposta, 404, "not_found", NOT_FOUND)


def test_sala_de_outra_pessoa_da_o_mesmo_404_de_sala_inexistente(ana: Any, bruno: Any) -> None:
    sala = _criar_sala(ana)

    resposta = logado(bruno).get(f"{ROOMS_URL}{sala['id']}/")

    _confere(resposta, 404, "not_found", NOT_FOUND)


# --- 405: método errado, com `Allow` preservado -----------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "url", "permitido", "proibido"),
    [
        ("delete", ROOMS_URL, "POST", "DELETE"),
        ("patch", ROOMS_URL, "GET", "PATCH"),
        ("post", WALLET_URL, "GET", "POST"),
    ],
)
def test_metodo_errado_da_405_e_mantem_o_cabecalho_allow(
    ana: Any, metodo: str, url: str, permitido: str, proibido: str
) -> None:
    resposta = getattr(logado(ana), metodo)(url, {}, format="json")

    _confere(resposta, 405, "method_not_allowed", METHOD_NOT_ALLOWED)
    metodos = {m.strip() for m in resposta["Allow"].split(",")}
    assert permitido in metodos
    assert proibido not in metodos


# --- 429: throttle por escopo, com `Retry-After` preservado -----------------------------------


def test_throttle_da_429_throttled_com_retry_after(bruno: Any) -> None:
    """A tentativa seguinte ao limite do escopo `invite_redeem` (lido da configuração) é barrada."""
    configuracao: Any = settings.REST_FRAMEWORK
    limite = int(configuracao["DEFAULT_THROTTLE_RATES"]["invite_redeem"].split("/")[0])
    respostas = [
        logado(bruno).post(JOIN_URL, {"code": f"palpite-{i}"}, format="json")
        for i in range(limite + 1)
    ]

    assert [r.status_code for r in respostas] == [404] * limite + [429]
    _confere(respostas[limite - 1], 404, "not_found", NOT_FOUND)  # a última dentro do limite
    _confere(respostas[limite], 429, "throttled", THROTTLED)
    espera = respostas[limite]["Retry-After"]
    assert re.fullmatch(r"\d+", espera)
    assert int(espera) > 0


# --- 403: CSRF da sessão ----------------------------------------------------------------------


def test_post_com_sessao_e_sem_token_csrf_da_403_permission_denied(ana: Any) -> None:
    from apps.rooms.models import Room

    resposta = com_sessao(ana).post(ROOMS_URL, {"name": "Amigos"}, format="json")

    _confere(resposta, 403, "permission_denied", PERMISSION_DENIED)
    assert Room.objects.count() == 0


def test_post_com_sessao_e_com_token_csrf_passa(ana: Any) -> None:
    """Controle do teste acima: o mesmo pedido COM o token funciona, então o 403 era o CSRF."""
    client = com_sessao(ana)
    client.get(CONFIG_URL)  # o servidor emite o cookie `csrftoken`
    token = client.cookies["csrftoken"].value

    resposta = client.post(ROOMS_URL, {"name": "Amigos"}, format="json", HTTP_X_CSRFTOKEN=token)

    assert resposta.status_code == 201


# --- 401/403: sem sessão e sem permissão ------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("get", ROOMS_URL), ("get", WALLET_URL), ("post", ROOMS_URL), ("post", DAILY_URL)],
)
def test_anonimo_da_403_not_authenticated(metodo: str, url: str) -> None:
    """Só há SessionAuthentication, que não tem `WWW-Authenticate`: o DRF devolve 403, não 401."""
    resposta = getattr(APIClient(), metodo)(url)

    _confere(resposta, 403, "not_authenticated", NOT_AUTHENTICATED)
    assert "WWW-Authenticate" not in resposta


def test_membro_comum_sem_poder_de_admin_da_403_permission_denied(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomMember

    sala = _criar_sala(ana)
    RoomMember.objects.create(room_id=sala["id"], user=bruno, role="member", status="active")

    resposta = logado(bruno).get(f"{ROOMS_URL}{sala['id']}/invites/")

    _confere(resposta, 403, "permission_denied", PERMISSION_DENIED)


# --- 406 e 415: negociação de conteúdo --------------------------------------------------------


def test_accept_que_a_api_nao_serve_da_406_not_acceptable() -> None:
    resposta = APIClient().get(CATALOG_URL, HTTP_ACCEPT="application/xml")

    _confere(resposta, 406, "not_acceptable", NOT_ACCEPTABLE)


def test_corpo_que_nao_e_json_da_415_unsupported_media_type(ana: Any) -> None:
    resposta = logado(ana).post(ROOMS_URL, data="name=Amigos", content_type="text/plain")

    _confere(resposta, 415, "unsupported_media_type", UNSUPPORTED_MEDIA_TYPE)


# --- 400 de validação: um código único, sem o detalhamento por campo ---------------------------
# Nenhum consumidor lê o detalhamento por campo desses 400 (o frontend só lê `ApiError.code`; os
# `fieldErrors` dele são do allauth), então ele não vira `details`: o contrato é só `code`.


@pytest.mark.parametrize("nome", ["", "   ", "x" * 200])
def test_nome_de_sala_invalido_da_400_invalid_request(ana: Any, nome: str) -> None:
    resposta = logado(ana).post(ROOMS_URL, {"name": nome}, format="json")

    _confere(resposta, 400, "invalid_request", INVALID_REQUEST)


def test_resgate_sem_codigo_da_400_invalid_request_e_nao_repassa_o_code_do_campo(
    bruno: Any,
) -> None:
    """O erro de campo se chama `code` e é uma LISTA: ele não pode passar por `code` de domínio."""
    resposta = logado(bruno).post(JOIN_URL, {}, format="json")

    _confere(resposta, 400, "invalid_request", INVALID_REQUEST)


def test_parametro_invalido_do_inventario_da_400_invalid_request(ana: Any) -> None:
    resposta = logado(ana).get(INVENTORY_URL, {"ordering": "owner"})

    _confere(resposta, 400, "invalid_request", INVALID_REQUEST)


# --- o que NÃO muda: erros de domínio e do allauth --------------------------------------------


def test_erro_de_dominio_da_diaria_segue_identico_com_available_at(ana: Any) -> None:
    primeira = logado(ana).post(DAILY_URL, {}, format="json")
    assert primeira.status_code == 201

    segunda = logado(ana).post(DAILY_URL, {}, format="json")

    assert segunda.status_code == 409
    corpo = segunda.json()
    assert set(corpo) == {"code", "message", "available_at"}
    assert corpo["code"] == "daily_not_ready"
    assert corpo["message"] != INVALID_REQUEST
    assert corpo["available_at"]


def test_erro_de_dominio_do_catalogo_segue_com_a_mensagem_propria(ana: Any) -> None:
    resposta = logado(ana).get(CATALOG_URL, {"ordering": "inventado"})

    _confere(resposta, 400, "invalid_ordering", "Ordenação inválida: inventado")


def test_detalhe_inexistente_do_catalogo_segue_com_o_proprio_404(ana: Any) -> None:
    resposta = logado(ana).get(f"{CATALOG_URL}{uuid.UUID(int=7)}/")

    _confere(resposta, 404, "not_found", NOT_FOUND)


def test_login_bloqueado_do_allauth_segue_no_formato_dele(ana: Any) -> None:
    """O allauth não é DRF: o handler não o alcança, e o frontend lê `errors[].code` dele."""
    client = APIClient(enforce_csrf_checks=True)
    client.get(CONFIG_URL)
    cabecalho: dict[str, Any] = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    login_url = "/_allauth/browser/v1/auth/login"
    senha_errada = {"username": "ana_01", "password": "senha-errada-123"}

    for _ in range(12):
        client.post(login_url, senha_errada, format="json", **cabecalho)
    resposta = client.post(login_url, senha_errada, format="json", **cabecalho)

    corpo = resposta.json()
    assert resposta.status_code in (400, 429)
    assert "code" not in corpo  # o `code` do allauth mora dentro de `errors`, não no topo
    assert "too_many_login_attempts" in [erro["code"] for erro in corpo["errors"]]
