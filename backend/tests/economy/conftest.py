"""Fixtures e helpers comuns dos testes da economia global (PR 2.2)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

WALLET_URL = "/api/v1/wallet/"
DAILY_URL = "/api/v1/wallet/daily/"

# Instante fixo de partida dos testes de relógio (o serviço recebe `now` por parâmetro).
T0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

User: Any = get_user_model()


def criar_usuario(username: str) -> Any:
    """Cria o usuário pelo ORM. A carteira nasce por sinal, como no cadastro de verdade."""
    return User.objects.create_user(
        username=username, email=f"{username}@exemplo.com", password="Tr0ub4dor&3-horse-battery"
    )


def logado(usuario: Any) -> APIClient:
    client = APIClient()
    client.force_authenticate(usuario)
    return client


@pytest.fixture
def ana() -> Any:
    return criar_usuario("ana_01")


@pytest.fixture
def bruno() -> Any:
    return criar_usuario("bruno_02")
