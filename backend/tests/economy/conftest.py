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


def jogador_sem_saldo_inicial(prefixo: str, *, depois_da_system: bool = False) -> tuple[Any, Any]:
    """Um jogador cuja carteira JÁ existe mas ainda não recebeu o saldo inicial.

    O app nunca produz esse estado (a carteira e o `starting_grant` nascem na mesma transação);
    o teste o fabrica para provar a regra de trava do `open_wallet`. O usuário entra por
    `bulk_create`, que não dispara o `post_save` (a carteira não nasce por sinal), e a carteira
    é criada à mão. Com `depois_da_system`, só serve a carteira de `id` MAIOR que o da `system`
    (a ordem em que o `post_entries` trava); o `id` é um UUID aleatório, então 40 tentativas
    bastam sempre.
    """
    from apps.economy.models import Wallet
    from apps.economy.services import get_system_wallet

    sistema = get_system_wallet()
    for i in range(40):
        usuario = User(username=f"{prefixo}_{i}", email=f"{prefixo}_{i}@exemplo.com")
        usuario.set_unusable_password()
        User.objects.bulk_create([usuario])
        carteira = Wallet.objects.create(user=usuario, kind="player")
        if not depois_da_system or carteira.id > sistema.id:
            return usuario, carteira
    raise AssertionError("nenhuma carteira com id maior que o da system em 40 tentativas")


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
