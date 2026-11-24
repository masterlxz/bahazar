"""Fixtures e helpers dos testes do inventário. Skins e jogadores inventados."""

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

INVENTORY_URL = "/api/v1/inventory/"

User: Any = get_user_model()


def url_de(username: str) -> str:
    return f"{INVENTORY_URL}{username}/"


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


def _relacao(de: Any, para: Any, status: str) -> Any:
    from apps.friends.models import Friendship

    return Friendship.objects.create(requester=de, addressee=para, status=status)


def tornar_amigos(a: Any, b: Any) -> Any:
    return _relacao(a, b, "accepted")


def pedir_amizade(de: Any, para: Any) -> Any:
    return _relacao(de, para, "pending")


def bloquear(quem_bloqueia: Any, bloqueado: Any) -> Any:
    return _relacao(quem_bloqueia, bloqueado, "blocked")


def criar_skin(
    external_id: str = "skin-1",
    *,
    minimo: str = "0",
    maximo: str = "1",
    ativa: bool = True,
    nome: str | None = None,
    arma: str = "AK-47",
    raridade: str = "Classified",
    preco: int = 1000,
) -> Any:
    from apps.catalog.models import Skin

    return Skin.objects.create(
        external_id=external_id,
        weapon=arma,
        name=nome or f"{arma} | Teste {external_id}",
        collection="Coleção Teste",
        rarity=raridade,
        min_float=Decimal(minimo),
        max_float=Decimal(maximo),
        reference_price=preco,
        active=ativa,
    )


@pytest.fixture
def skin() -> Any:
    return criar_skin()


def criar_instancia(dono: Any, skin: Any, float_value: str = "0.5") -> Any:
    """Grava direto pelo ORM, só para montar cenário de teste."""
    from apps.inventory.models import SkinInstance

    return SkinInstance.objects.create(
        owner=dono, skin=skin, float_value=Decimal(float_value), acquired_via="admin_grant"
    )
