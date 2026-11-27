"""Fixtures e helpers dos testes do formato de erro da API (`{code, message}`)."""

from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.exceptions import api_exception_handler

ROOMS_URL = "/api/v1/rooms/"
JOIN_URL = "/api/v1/rooms/join/"
WALLET_URL = "/api/v1/wallet/"
DAILY_URL = "/api/v1/wallet/daily/"
INVENTORY_URL = "/api/v1/inventory/"
CATALOG_URL = "/api/v1/catalog/skins/"
CONFIG_URL = "/_allauth/browser/v1/config"

User: Any = get_user_model()

ApiExceptionHandler = Callable[[Exception, dict[str, Any]], Any]


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    """O limite de tentativas (throttle) e o do login moram no cache: isola um teste do outro."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def handler() -> ApiExceptionHandler:
    """O `EXCEPTION_HANDLER` da API."""
    return api_exception_handler


def criar_usuario(username: str) -> Any:
    return User.objects.create_user(
        username=username, email=f"{username}@exemplo.com", password="Tr0ub4dor&3-horse-battery"
    )


def logado(usuario: Any) -> APIClient:
    """Autenticado sem sessão (`force_authenticate` pula o CSRF; o CSRF tem cliente próprio)."""
    client = APIClient()
    client.force_authenticate(usuario)
    return client


def com_sessao(usuario: Any) -> APIClient:
    """Cliente de navegador: sessão de verdade e CSRF exigido, como em produção."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(usuario)
    return client


def criar_skin(external_id: str = "skin-1") -> Any:
    from apps.catalog.models import Skin

    return Skin.objects.create(
        external_id=external_id,
        weapon="AK-47",
        name=f"AK-47 | Teste {external_id}",
        collection="Coleção Teste",
        rarity="Classified",
        min_float=Decimal(0),
        max_float=Decimal(1),
        reference_price=1000,
        active=True,
    )


@pytest.fixture
def ana(db: None) -> Any:
    return criar_usuario("ana_01")


@pytest.fixture
def bruno(db: None) -> Any:
    return criar_usuario("bruno_02")
