"""Padrões seguros: negar por omissão e configuração de produção sem segredo no código."""

import importlib
import sys
from types import ModuleType

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.test import APIClient


def test_permissao_padrao_do_drf_exige_autenticacao() -> None:
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]


@override_settings(ROOT_URLCONF="tests.urls_sem_permissao")
def test_view_sem_permissao_explicita_nega_anonimo() -> None:
    response = APIClient().get("/sem-permissao/")

    assert response.status_code in (401, 403)


def _carregar_prod(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    for nome in ("DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS"):
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in env.items():
        monkeypatch.setenv(nome, valor)
    sys.modules.pop("config.settings.prod", None)
    return importlib.import_module("config.settings.prod")


def test_prod_recusa_subir_sem_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ImproperlyConfigured):
        _carregar_prod(monkeypatch, DJANGO_ALLOWED_HOSTS="api.exemplo.com")


def test_prod_recusa_subir_sem_allowed_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ImproperlyConfigured):
        _carregar_prod(monkeypatch, DJANGO_SECRET_KEY="x" * 50)


def test_prod_ativa_protecoes(monkeypatch: pytest.MonkeyPatch) -> None:
    prod = _carregar_prod(
        monkeypatch,
        DJANGO_SECRET_KEY="x" * 50,
        DJANGO_ALLOWED_HOSTS="api.exemplo.com,www.exemplo.com",
    )

    assert prod.DEBUG is False
    assert prod.ALLOWED_HOSTS == ["api.exemplo.com", "www.exemplo.com"]
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SECURE_HSTS_SECONDS >= 31536000
