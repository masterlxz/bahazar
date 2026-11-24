"""Fixtures e helpers dos testes do inventário (PR 3.2a). Skins e jogadores inventados."""

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model

User: Any = get_user_model()


def criar_usuario(username: str) -> Any:
    return User.objects.create_user(
        username=username, email=f"{username}@exemplo.com", password="Tr0ub4dor&3-horse-battery"
    )


@pytest.fixture
def ana() -> Any:
    return criar_usuario("ana_01")


@pytest.fixture
def bruno() -> Any:
    return criar_usuario("bruno_02")


def criar_skin(
    external_id: str = "skin-1",
    *,
    minimo: str = "0",
    maximo: str = "1",
    ativa: bool = True,
) -> Any:
    from apps.catalog.models import Skin

    return Skin.objects.create(
        external_id=external_id,
        weapon="AK-47",
        name=f"AK-47 | Teste {external_id}",
        collection="",
        rarity="Classified",
        min_float=Decimal(minimo),
        max_float=Decimal(maximo),
        reference_price=1000,
        active=ativa,
    )


@pytest.fixture
def skin() -> Any:
    return criar_skin()


def criar_instancia(dono: Any, skin: Any, float_value: str = "0.5") -> Any:
    """Grava direto pelo ORM, só para montar cenário de teste do banco."""
    from apps.inventory.models import SkinInstance

    return SkinInstance.objects.create(
        owner=dono, skin=skin, float_value=Decimal(float_value), acquired_via="admin_grant"
    )
