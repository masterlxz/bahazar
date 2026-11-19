"""Fixtures e helpers comuns dos testes de salas.

Os testes montam o cenário pela API (POST /rooms/) sempre que possível: assim eles exercitam o
mesmo caminho que o frontend. A autenticação usa `force_authenticate`; o CSRF da sessão já é
coberto em `tests/accounts`.
"""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

ROOMS_URL = "/api/v1/rooms/"

User: Any = get_user_model()


def detalhe_url(sala_id: str) -> str:
    return f"{ROOMS_URL}{sala_id}/"


def sair_url(sala_id: str) -> str:
    return f"{ROOMS_URL}{sala_id}/leave/"


def criar_usuario(username: str) -> Any:
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


def criar_sala_pela_api(usuario: Any, nome: str = "Amigos") -> dict[str, Any]:
    resposta = logado(usuario).post(ROOMS_URL, {"name": nome}, format="json")
    assert resposta.status_code == 201, resposta.content
    dados: dict[str, Any] = resposta.json()
    return dados
