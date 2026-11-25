"""Fixtures e helpers dos testes de troca de itens. Jogadores e skins inventados."""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model

User: Any = get_user_model()


def criar_usuario(username: str) -> Any:
    return User.objects.create_user(
        username=username, email=f"{username}@exemplo.com", password="Tr0ub4dor&3-horse-battery"
    )


def criar_relacao(de: Any, para: Any, status: str) -> Any:
    from apps.friends.models import Friendship

    return Friendship.objects.create(requester=de, addressee=para, status=status)


def tornar_amigos(a: Any, b: Any) -> Any:
    return criar_relacao(a, b, "accepted")


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


def criar_instancia(
    dono: Any, skin: Any, float_value: str = "0.5", *, pk: uuid.UUID | None = None
) -> Any:
    """Grava direto pelo ORM, só para montar cenário. `pk` fixa a ordem dos UUIDs nos testes de
    ordem de trava."""
    from apps.inventory.models import SkinInstance

    return SkinInstance.objects.create(
        id=pk or uuid.uuid4(),
        owner=dono,
        skin=skin,
        float_value=Decimal(float_value),
        acquired_via="admin_grant",
    )


@pytest.fixture
def skin() -> Any:
    return criar_skin()


@pytest.fixture
def cena(skin: Any) -> SimpleNamespace:
    """ana e bruno são amigos; carla existe, sem amizade com ninguém.

    ana tem a1 (float 0,123456789: distintivo, para provar que o aceite não mexe nele) e a2;
    bruno tem b1 e b2; carla tem c1.
    """
    ana, bruno, carla = (criar_usuario(n) for n in ("ana_01", "bruno_02", "carla_03"))
    tornar_amigos(ana, bruno)
    return SimpleNamespace(
        ana=ana,
        bruno=bruno,
        carla=carla,
        a1=criar_instancia(ana, skin, "0.123456789"),
        a2=criar_instancia(ana, skin, "0.900000000"),
        b1=criar_instancia(bruno, skin, "0.250000000"),
        b2=criar_instancia(bruno, skin, "0.750000000"),
        c1=criar_instancia(carla, skin, "0.500000000"),
    )
