"""Formato único de erro da API: `{code, message}` (EXCEPTION_HANDLER do DRF).

As exceções de domínio já saem assim (as views montam `{code, message}`), mas os erros do próprio
DRF saíam como `{"detail": "..."}`: JSON quebrado, `?page` inválida, CSRF, 405, 429, sem sessão.
O frontend lê `ApiError.code`, então esses caíam no erro genérico. Este handler dá a eles um `code`
estável e uma `message` fixa em português (sem repassar o texto da exceção). O status e os
cabeçalhos (`Allow`, `Retry-After`, `WWW-Authenticate`) são os do DRF, intactos: só o corpo troca.

Erro de validação (`ValidationError`) vira `invalid_request` sem o detalhamento por campo: nenhuma
view o devolve para um consumidor ler (o frontend só lê `code`), e `details` seria contrato sem uso.
"""

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

# (classes, code, message). A ordem não importa: nenhuma classe daqui herda de outra daqui.
_MAPA: tuple[tuple[tuple[type[Exception], ...], str, str], ...] = (
    ((exceptions.ParseError,), "parse_error", "O corpo da requisição não é um JSON válido."),
    ((exceptions.NotFound, Http404), "not_found", "Não encontrado."),
    ((exceptions.MethodNotAllowed,), "method_not_allowed", "Método não permitido."),
    (
        (exceptions.Throttled,),
        "throttled",
        "Muitas requisições. Tente novamente em instantes.",
    ),
    (
        # Inclui o 403 do CSRF da SessionAuthentication (ela levanta PermissionDenied).
        (exceptions.PermissionDenied, DjangoPermissionDenied),
        "permission_denied",
        "Você não tem permissão para realizar esta ação.",
    ),
    (
        (exceptions.NotAuthenticated, exceptions.AuthenticationFailed),
        "not_authenticated",
        "Autenticação necessária.",
    ),
    ((exceptions.NotAcceptable,), "not_acceptable", "Formato de resposta não suportado."),
    (
        (exceptions.UnsupportedMediaType,),
        "unsupported_media_type",
        "Formato do corpo não suportado.",
    ),
    ((exceptions.ValidationError,), "invalid_request", "Requisição inválida."),
)

# Qualquer outra `APIException` (a nossa, de um app novo, ou de terceiros): o código é genérico,
# o status continua o dela.
_OUTRO = ("error", "Não foi possível processar a requisição.")


def _ja_e_erro_de_dominio(exc: Exception, dados: Any) -> bool:
    """A exceção já carrega `{code, message}` nosso: o corpo fica como está.

    Um `ValidationError` com campo chamado `code` NÃO conta (é erro de campo, não de domínio): em
    `JoinRoomView` esse campo é uma lista, e com texto o `ErrorDetail` também é `str`.
    """
    return (
        not isinstance(exc, exceptions.ValidationError)
        and isinstance(dados, dict)
        and isinstance(dados.get("code"), str)
    )


def _code_e_message(exc: Exception) -> tuple[str, str]:
    for classes, code, message in _MAPA:
        if isinstance(exc, classes):
            return code, message
    return _OUTRO


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Troca o corpo dos erros do DRF por `{code, message}`; `None` (500) segue com o Django."""
    resposta = exception_handler(exc, context)
    if resposta is None:
        return None
    if _ja_e_erro_de_dominio(exc, resposta.data):
        return resposta
    code, message = _code_e_message(exc)
    resposta.data = {"code": code, "message": message}
    return resposta
