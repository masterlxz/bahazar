"""O `EXCEPTION_HANDLER` da API isolado: o mapa de exceção para `{code, message}`.

As rotas reais estão em `test_api_errors.py`; aqui ficam as ramificações que nenhuma rota atual
provoca (exceção de domínio com `code`, `APIException` sem mapa, exceção que não é da API).
"""

from typing import Any

import pytest
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAcceptable,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)

from .conftest import ApiExceptionHandler


class ErroDeDominio(APIException):
    """Exceção nossa que já carrega `{code, message}` no detalhe: o handler não a reescreve."""

    status_code = status.HTTP_409_CONFLICT


class NaoAutenticadoComCabecalho(NotAuthenticated):
    """Como a view deixa a exceção quando o autenticador tem `WWW-Authenticate` (aí é 401)."""

    auth_header = 'Bearer realm="api"'


class ErroSemMapa(APIException):
    """Uma `APIException` que o mapa não conhece, com status próprio."""

    status_code = status.HTTP_418_IM_A_TEAPOT
    default_detail = "I'm a teapot."


def test_excecao_que_nao_e_da_api_devolve_none(handler: ApiExceptionHandler) -> None:
    """`None` deixa o 500 com o tratamento do Django (log e página de erro), sem corpo nosso."""
    assert handler(ValueError("estourou"), {}) is None
    assert handler(KeyError("x"), {}) is None


@pytest.mark.parametrize(
    ("excecao", "http_status", "code"),
    [
        (ParseError(), 400, "parse_error"),
        (NotFound(), 404, "not_found"),
        (Http404(), 404, "not_found"),
        (MethodNotAllowed("PUT"), 405, "method_not_allowed"),
        (Throttled(), 429, "throttled"),
        (PermissionDenied(), 403, "permission_denied"),
        (DjangoPermissionDenied(), 403, "permission_denied"),
        (NotAuthenticated(), 401, "not_authenticated"),
        (AuthenticationFailed(), 401, "not_authenticated"),
        (NotAcceptable(), 406, "not_acceptable"),
        (UnsupportedMediaType("text/plain"), 415, "unsupported_media_type"),
        (ValidationError({"name": ["Este campo é obrigatório."]}), 400, "invalid_request"),
        (ValidationError(["lista solta"]), 400, "invalid_request"),
        (ErroSemMapa(), 418, "error"),
    ],
)
def test_cada_excecao_vira_status_e_code_estaveis(
    handler: ApiExceptionHandler, excecao: Exception, http_status: int, code: str
) -> None:
    resposta = handler(excecao, {})

    assert resposta.status_code == http_status
    assert set(resposta.data) == {"code", "message"}
    assert resposta.data["code"] == code
    assert isinstance(resposta.data["message"], str)
    assert resposta.data["message"].strip()


def test_texto_da_excecao_nao_vaza_para_a_mensagem(handler: ApiExceptionHandler) -> None:
    """A `message` é fixa em português; o texto em inglês do DRF (ou o de quem lançou) não passa."""
    resposta = handler(ParseError("JSON parse error - Expecting value: line 1 column 1"), {})

    assert resposta.data == {
        "code": "parse_error",
        "message": "O corpo da requisição não é um JSON válido.",
    }


def test_throttle_preserva_retry_after(handler: ApiExceptionHandler) -> None:
    resposta = handler(Throttled(wait=30), {})

    assert resposta.status_code == 429
    assert resposta["Retry-After"] == "30"
    assert resposta.data["code"] == "throttled"


def test_401_preserva_www_authenticate(handler: ApiExceptionHandler) -> None:
    """A view põe `auth_header` quando o autenticador tem cabeçalho; o corpo muda, ele não."""
    resposta = handler(NaoAutenticadoComCabecalho(), {})

    assert resposta.status_code == 401
    assert resposta["WWW-Authenticate"] == 'Bearer realm="api"'
    assert resposta.data["code"] == "not_authenticated"


def test_excecao_de_dominio_com_code_fica_intacta(handler: ApiExceptionHandler) -> None:
    detalhe = {"code": "self_trade", "message": "Você não pode trocar consigo."}

    resposta = handler(ErroDeDominio(detalhe), {})

    assert resposta.status_code == 409
    assert dict(resposta.data) == detalhe


def test_excecao_de_dominio_preserva_chaves_extras(handler: ApiExceptionHandler) -> None:
    detalhe = {"code": "daily_not_ready", "message": "Ainda não.", "available_at": "2026-11-28"}

    resposta = handler(ErroDeDominio(detalhe), {})

    assert dict(resposta.data) == detalhe


def test_validation_error_com_campo_chamado_code_nao_e_tomado_por_dominio(
    handler: ApiExceptionHandler,
) -> None:
    """Campo `code` com TEXTO (não lista) num `ValidationError` é erro de campo, não de domínio."""
    resposta = handler(ValidationError({"code": "Informe o código."}), {})

    assert resposta.status_code == 400
    assert resposta.data == {"code": "invalid_request", "message": "Requisição inválida."}


def test_detalhe_sem_code_de_excecao_sem_mapa_vira_code_error(
    handler: ApiExceptionHandler,
) -> None:
    resposta: Any = handler(ErroSemMapa({"outro": "formato"}), {})

    assert resposta.status_code == 418
    assert resposta.data["code"] == "error"
    assert "outro" not in resposta.data
