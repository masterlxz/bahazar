"""Fixtures e helpers comuns dos testes de amizades (PR 2.3).

O cenário é montado pela API sempre que possível, para exercitar o mesmo caminho do frontend.
"""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

FRIENDS_URL = "/api/v1/friends/"
REQUESTS_URL = "/api/v1/friends/requests/"
SENT_URL = "/api/v1/friends/requests/sent/"

User: Any = get_user_model()


def perfil_url(username: str) -> str:
    return f"{FRIENDS_URL}{username}/"


def bloqueio_url(username: str) -> str:
    return f"{FRIENDS_URL}{username}/block/"


def aceitar_url(pedido_id: str) -> str:
    return f"{REQUESTS_URL}{pedido_id}/accept/"


def recusar_url(pedido_id: str) -> str:
    return f"{REQUESTS_URL}{pedido_id}/decline/"


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


@pytest.fixture
def carla() -> Any:
    return criar_usuario("carla_03")


def pedir(de: Any, para: Any) -> dict[str, Any]:
    """`de` pede amizade a `para` pela API e devolve o pedido criado."""
    resposta = logado(de).post(REQUESTS_URL, {"username": para.username}, format="json")
    assert resposta.status_code == 201, resposta.content
    dados: dict[str, Any] = resposta.json()
    return dados


def tornar_amigos(a: Any, b: Any) -> None:
    pedido = pedir(a, b)
    resposta = logado(b).post(aceitar_url(pedido["id"]))
    assert resposta.status_code == 200, resposta.content
