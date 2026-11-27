"""Transferência com um jogador desativado (`is_active=False`): `PlayerUnavailable` (J4).

Decisão do dono (2026-11-27): a regra vale em `transfer` mesmo sem rota e sem chamador hoje.
O jogador é desativado direto no banco (`.update`), de propósito: os objetos `User` em memória
seguem com `is_active=True`, então só uma leitura do banco passa.
"""

import uuid
from typing import Any

import pytest
from django.contrib.auth import get_user_model

from apps.economy import audit, services
from apps.economy.models import IdempotencyRecord, Wallet, WalletTransaction

# As fixtures `ana` e `bruno` vêm do conftest deste pacote.
pytestmark = pytest.mark.django_db

SALDO_INICIAL = 2_500  # US$ 25,00 (ADR 0013)
User: Any = get_user_model()


def _chave() -> str:
    return str(uuid.uuid4())


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def _desativar(usuario: Any) -> None:
    User.objects.filter(pk=usuario.pk).update(is_active=False)


def _nada_mudou(ana: Any, bruno: Any) -> None:
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL, SALDO_INICIAL)
    assert WalletTransaction.objects.filter(kind="transfer").count() == 0
    assert audit.check_ledger() == []


def test_transferir_para_desativado_e_recusado_e_nada_se_move(ana: Any, bruno: Any) -> None:
    _desativar(bruno)

    with pytest.raises(services.PlayerUnavailable):
        services.transfer(ana, bruno, 1_000, idempotency_key=_chave())

    _nada_mudou(ana, bruno)


def test_transferir_estando_desativado_tambem_e_recusado(ana: Any, bruno: Any) -> None:
    _desativar(ana)

    with pytest.raises(services.PlayerUnavailable):
        services.transfer(ana, bruno, 1_000, idempotency_key=_chave())

    _nada_mudou(ana, bruno)


def test_a_recusa_nao_queima_a_chave_e_reativado_a_mesma_chave_transfere(
    ana: Any, bruno: Any
) -> None:
    chave = _chave()
    _desativar(bruno)
    with pytest.raises(services.PlayerUnavailable):
        services.transfer(ana, bruno, 1_000, idempotency_key=chave)
    assert IdempotencyRecord.objects.count() == 0
    User.objects.filter(pk=bruno.pk).update(is_active=True)

    resultado = services.transfer(ana, bruno, 1_000, idempotency_key=chave)

    assert resultado.replayed is False
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - 1_000, SALDO_INICIAL + 1_000)
