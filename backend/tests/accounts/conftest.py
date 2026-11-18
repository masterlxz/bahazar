"""Fixtures e constantes comuns dos testes de autenticação."""

from collections.abc import Iterator
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

BASE = "/_allauth/browser/v1"
CONFIG_URL = f"{BASE}/config"
SIGNUP_URL = f"{BASE}/auth/signup"
LOGIN_URL = f"{BASE}/auth/login"
SESSION_URL = f"{BASE}/auth/session"
ME_URL = "/api/v1/me/"

SENHA_FORTE = "Tr0ub4dor&3-horse-battery"

User: Any = get_user_model()


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    """O limitador de tentativas do allauth usa o cache: isola um teste do outro."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client() -> APIClient:
    """Cliente que EXIGE CSRF, como um navegador de verdade (o padrão do APIClient o dispensa)."""
    return APIClient(enforce_csrf_checks=True)


def csrf_headers(client: APIClient) -> dict[str, Any]:
    """Obtém o token CSRF como o frontend faria (cookie `csrftoken`) e devolve o cabeçalho."""
    client.get(CONFIG_URL)
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def criar_usuario(
    username: str = "ana_01",
    email: str = "ana@exemplo.com",
    password: str = SENHA_FORTE,
) -> Any:
    return User.objects.create_user(username=username, email=email, password=password)
