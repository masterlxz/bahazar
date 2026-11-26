"""Fixtures e helpers comuns dos testes da economia global (PR 2.2)."""

import uuid
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


ID_BAIXO_DA_SYSTEM = uuid.UUID(int=2**128 - 1)


def system_com_id_baixo() -> Any:
    """A carteira `system` com `id` fixo e mínimo (`UUID(int=1)`), criada ANTES dos jogadores.

    O `post_entries` trava as carteiras por `id` crescente. Com a `system` no começo da fila, a
    carteira de qualquer jogador (um UUID aleatório) vem DEPOIS dela, sempre: é a ordem em que a
    compra trava e que forma o ciclo dos testes de deadlock. Sortear jogadores até achar um com
    `id` maior falhava em ~2,4% das execuções (`E[s^40] = 1/41`), pois o `id` da `system` também
    era aleatório. Se a `system` já existir com outro `id` (um jogador criado antes dela), o
    teste falha na hora, em vez de depender de sorte.
    """
    from apps.economy.models import Wallet

    sistema, _ = Wallet.objects.get_or_create(kind="system", defaults={"id": ID_BAIXO_DA_SYSTEM})
    assert sistema.id == ID_BAIXO_DA_SYSTEM, "crie a system com id baixo ANTES de criar jogadores"
    return sistema


def jogador_sem_saldo_inicial(prefixo: str, *, depois_da_system: bool = False) -> tuple[Any, Any]:
    """Um jogador cuja carteira JÁ existe mas ainda não recebeu o saldo inicial.

    O app nunca produz esse estado (a carteira e o `starting_grant` nascem na mesma transação);
    o teste o fabrica para provar a regra de trava do `open_wallet`. O usuário entra por
    `bulk_create`, que não dispara o `post_save` (a carteira não nasce por sinal), e a carteira
    é criada à mão. Com `depois_da_system`, a `system` nasce com `id` baixo
    (`system_com_id_baixo`, que exige ser a PRIMEIRA carteira do teste) e a do jogador fica
    depois dela na ordem do `post_entries`; sem ele, a `system` pode ser a que já existir.
    """
    from apps.economy.models import Wallet
    from apps.economy.services import get_system_wallet

    sistema = system_com_id_baixo() if depois_da_system else get_system_wallet()
    usuario = User(username=prefixo, email=f"{prefixo}@exemplo.com")
    usuario.set_unusable_password()
    User.objects.bulk_create([usuario])
    carteira = Wallet.objects.create(user=usuario, kind="player")
    if depois_da_system:
        assert carteira.id > sistema.id
    return usuario, carteira


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
