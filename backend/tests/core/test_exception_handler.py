"""O `EXCEPTION_HANDLER` da API isolado: o mapa de exceção para `{code, message}`.

As rotas reais estão em `test_api_errors.py`; aqui ficam as ramificações que nenhuma rota atual
provoca (`APIException` sem mapa, exceção que não é da API, cabeçalhos).
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
        "message": "O corpo da requisição é inválido.",
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


def test_validation_error_com_campo_chamado_code_vira_invalid_request(
    handler: ApiExceptionHandler,
) -> None:
    """Um campo se chamar `code` (texto ou lista) não muda nada: o corpo é o do mapa."""
    for detalhe in ({"code": "Informe o código."}, {"code": ["Informe o código."]}):
        resposta = handler(ValidationError(detalhe), {})

        assert resposta.status_code == 400
        assert resposta.data == {"code": "invalid_request", "message": "Requisição inválida."}


def test_detalhe_da_excecao_nunca_vaza_nem_com_chave_code(handler: ApiExceptionHandler) -> None:
    """Toda exceção passa pelo mapa: o detalhe dela (até um `{code, message}`) não é repassado."""
    detalhes: list[dict[str, Any]] = [{"outro": "formato"}, {"code": "x", "message": "y", "n": 1}]
    for detalhe in detalhes:
        resposta: Any = handler(ErroSemMapa(detalhe), {})

        assert resposta.status_code == 418
        assert resposta.data == {
            "code": "error",
            "message": "Não foi possível processar a requisição.",
        }
