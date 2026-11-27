"""Formato `{code, message}` dos erros levantados no DRF (EXCEPTION_HANDLER).

Os erros do próprio DRF saíam como `{"detail": "..."}`: JSON quebrado, `?page` inválida, CSRF, 405,
429, sem sessão. O frontend lê `ApiError.code`, então esses caíam no erro genérico. Este handler dá
a TODA exceção que chega a ele um `code` estável e uma `message` fixa em português (o texto da
exceção não é repassado). O status e os cabeçalhos (`Allow`, `Retry-After`, `WWW-Authenticate`) são
os do DRF, intactos: só o corpo troca.

`ValidationError` vira `invalid_request` e perde o detalhamento por campo (`{"name": [...]}`): o
frontend só lê `code`, e `details` seria contrato sem consumidor.

Ficam FORA do handler, porque não são exceções que chegam a ele: as respostas `Response({code,
message})` que as views montam direto, o 400 de `friends/views.py` (`{"username": [...]}`) e os
erros do allauth (`errors[].code`), que não é DRF.
"""

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

# (classes, code, message). A ordem não importa: nenhuma classe daqui herda de outra daqui.
_MAPA: tuple[tuple[tuple[type[Exception], ...], str, str], ...] = (
    # Neutra: o DRF também levanta `ParseError` em multipart malformado, não só em JSON.
    ((exceptions.ParseError,), "parse_error", "O corpo da requisição é inválido."),
    ((exceptions.NotFound, Http404), "not_found", "Não encontrado."),
    ((exceptions.MethodNotAllowed,), "method_not_allowed", "Método não permitido."),
    (
        (KeyError,),
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

# Qualquer outra `APIException` (de um app novo ou de terceiros): o código é genérico, o status
# continua o dela.
_OUTRO = ("error", "Não foi possível processar a requisição.")


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
    code, message = _code_e_message(exc)
    resposta.data = {"code": code, "message": message}
    return resposta
