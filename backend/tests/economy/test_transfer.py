"""Transferência entre jogadores: uma vez por chave, soma zero, sem rota HTTP (PR 4.1)."""

import uuid
from typing import Any

import pytest
from django.db.models import Sum

from apps.economy import audit, idempotency, rules, services
from apps.economy.models import IdempotencyRecord, Wallet, WalletTransaction

from .conftest import criar_usuario, logado

pytestmark = pytest.mark.django_db

SALDO_INICIAL = 2_500  # US$ 25,00 (ADR 0013)


def _chave() -> str:
    return str(uuid.uuid4())


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def _saldo_do_sistema() -> int:
    return Wallet.objects.get(kind="system").balance


def _grupos_de_transferencia() -> int:
    return WalletTransaction.objects.filter(kind="transfer").values("group_id").distinct().count()


def test_transferencia_move_o_valor_e_lanca_duas_linhas_que_somam_zero(
    ana: Any, bruno: Any
) -> None:
    resultado = services.transfer(ana, bruno, 1_000, idempotency_key=_chave())

    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - 1_000, SALDO_INICIAL + 1_000)
    assert (resultado.amount, resultado.replayed) == (1_000, False)
    linhas = WalletTransaction.objects.filter(group_id=resultado.ledger_group_id)
    assert {(t.wallet.user_id, t.amount, t.kind) for t in linhas} == {
        (ana.pk, -1_000, "transfer"),
        (bruno.pk, 1_000, "transfer"),
    }
    assert linhas.aggregate(total=Sum("amount"))["total"] == 0
    assert _saldo_do_sistema() == -2 * SALDO_INICIAL  # a transferência não cria nem destrói moeda
    assert audit.check_ledger() == []


def test_pode_transferir_o_saldo_inteiro_e_ficar_com_zero(ana: Any, bruno: Any) -> None:
    services.transfer(ana, bruno, SALDO_INICIAL, idempotency_key=_chave())

    assert (_saldo(ana), _saldo(bruno)) == (0, 2 * SALDO_INICIAL)


def test_saldo_insuficiente_recusa_sem_gravar_nada_e_nao_queima_a_chave(
    ana: Any, bruno: Any
) -> None:
    chave = _chave()

    with pytest.raises(services.InsufficientFunds):
        services.transfer(ana, bruno, SALDO_INICIAL + 1, idempotency_key=chave)

    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL, SALDO_INICIAL)
    assert _grupos_de_transferencia() == 0
    assert IdempotencyRecord.objects.count() == 0
    # A mesma chave ainda serve para uma tentativa que cabe no saldo.
    services.transfer(ana, bruno, 100, idempotency_key=chave)
    assert _saldo(ana) == SALDO_INICIAL - 100


def test_repetir_a_mesma_transferencia_devolve_o_resultado_original(ana: Any, bruno: Any) -> None:
    chave = _chave()
    primeira = services.transfer(ana, bruno, 700, idempotency_key=chave)

    segunda = services.transfer(ana, bruno, 700, idempotency_key=chave)

    assert segunda.replayed is True
    assert segunda.ledger_group_id == primeira.ledger_group_id
    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - 700, SALDO_INICIAL + 700)  # uma vez só
    assert _grupos_de_transferencia() == 1


def test_mesma_chave_com_outro_valor_e_recusada_e_nao_move_dinheiro(ana: Any, bruno: Any) -> None:
    chave = _chave()
    services.transfer(ana, bruno, 700, idempotency_key=chave)

    with pytest.raises(idempotency.IdempotencyKeyReused):
        services.transfer(ana, bruno, 800, idempotency_key=chave)

    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL - 700, SALDO_INICIAL + 700)
    assert _grupos_de_transferencia() == 1


def test_mesma_chave_com_outro_destinatario_e_recusada(ana: Any, bruno: Any) -> None:
    carla = criar_usuario("carla_03")
    chave = _chave()
    services.transfer(ana, bruno, 700, idempotency_key=chave)

    with pytest.raises(idempotency.IdempotencyKeyReused):
        services.transfer(ana, carla, 700, idempotency_key=chave)

    assert _saldo(carla) == SALDO_INICIAL
    assert _grupos_de_transferencia() == 1


def test_a_chave_vale_por_remetente_e_dois_remetentes_podem_usar_a_mesma(
    ana: Any, bruno: Any
) -> None:
    carla = criar_usuario("carla_03")
    chave = _chave()

    services.transfer(ana, carla, 300, idempotency_key=chave)
    services.transfer(bruno, carla, 400, idempotency_key=chave)

    assert _saldo(carla) == SALDO_INICIAL + 700
    assert _grupos_de_transferencia() == 2
    assert IdempotencyRecord.objects.count() == 2
    assert audit.check_ledger() == []


def test_chave_do_ledger_leva_o_remetente_para_nao_colidir_na_carteira_do_destinatario(
    ana: Any, bruno: Any
) -> None:
    carla = criar_usuario("carla_03")
    chave = _chave()
    services.transfer(ana, carla, 300, idempotency_key=chave)
    services.transfer(bruno, carla, 400, idempotency_key=chave)

    chaves_da_carla = set(
        WalletTransaction.objects.filter(wallet__user=carla, kind="transfer").values_list(
            "idempotency_key", flat=True
        )
    )

    assert chaves_da_carla == {f"transfer:{ana.pk}:{chave}", f"transfer:{bruno.pk}:{chave}"}


def test_transferir_para_si_mesmo_e_recusado(ana: Any) -> None:
    with pytest.raises(services.InvalidTransfer):
        services.transfer(ana, ana, 100, idempotency_key=_chave())

    assert _saldo(ana) == SALDO_INICIAL
    assert _grupos_de_transferencia() == 0


@pytest.mark.parametrize("valor", [0, -1, -2_500, rules.BIGINT_MAX + 1, True, 1.5, "100", None])
def test_valor_invalido_e_recusado_sem_gravar(ana: Any, bruno: Any, valor: Any) -> None:
    with pytest.raises(services.InvalidTransfer):
        services.transfer(ana, bruno, valor, idempotency_key=_chave())

    assert (_saldo(ana), _saldo(bruno)) == (SALDO_INICIAL, SALDO_INICIAL)
    assert IdempotencyRecord.objects.count() == 0


@pytest.mark.parametrize("chave", ["", "abc", "x" * 101, "7f3a9c2e-1b4d-4e8a-9c3d-5a6b7c8d9e0g"])
def test_chave_que_nao_e_uuid_e_recusada(ana: Any, bruno: Any, chave: str) -> None:
    with pytest.raises(ValueError):
        services.transfer(ana, bruno, 100, idempotency_key=chave)

    assert _grupos_de_transferencia() == 0


def test_chave_em_maiusculas_e_a_mesma_chave(ana: Any, bruno: Any) -> None:
    chave = _chave()
    services.transfer(ana, bruno, 100, idempotency_key=chave)

    repetida = services.transfer(ana, bruno, 100, idempotency_key=chave.upper())

    assert repetida.replayed is True
    assert _saldo(ana) == SALDO_INICIAL - 100


@pytest.mark.parametrize(
    "rota", ["/api/v1/wallet/transfer/", "/api/v1/transfer/", "/api/v1/transfers/"]
)
def test_a_transferencia_nao_tem_rota_http(ana: Any, bruno: Any, rota: str) -> None:
    """Decisão do dono (2026-11-25): só serviço interno; sem rota, sem caminho de farm (J4)."""
    resposta = logado(ana).post(rota, {"to": bruno.username, "amount": 100}, format="json")

    assert resposta.status_code == 404
    assert _saldo(ana) == SALDO_INICIAL
