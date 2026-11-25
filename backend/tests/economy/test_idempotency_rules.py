"""Regras puras da idempotência (sem banco): a chave é um UUID e o hash do pedido é estável."""

import hashlib
from typing import Any

import pytest

from apps.economy import rules

CHAVE = "7f3a9c2e-1b4d-4e8a-9c3d-5a6b7c8d9e0f"


def test_chave_uuid_e_normalizada_para_minusculas() -> None:
    assert rules.normalize_idempotency_key(CHAVE.upper()) == CHAVE


def test_chave_uuid_sem_hifens_vira_a_forma_canonica() -> None:
    assert rules.normalize_idempotency_key(CHAVE.replace("-", "")) == CHAVE


@pytest.mark.parametrize(
    "chave",
    [
        "",
        "abc",
        "123",
        CHAVE[:-1],  # um dígito a menos
        CHAVE + "0",  # um dígito a mais
        CHAVE[:-1] + "g",  # fora do alfabeto hexadecimal
        "x" * 101,
        f"{CHAVE}; drop table",
        "../../etc/passwd",
        None,
        123,
    ],
)
def test_chave_que_nao_e_uuid_e_recusada(chave: Any) -> None:
    with pytest.raises(ValueError):
        rules.normalize_idempotency_key(chave)


def test_hash_do_pedido_e_o_sha256_de_uma_lista_json_canonica() -> None:
    esperado = hashlib.sha256(b'["transfer","a","b",100]').hexdigest()

    assert rules.request_fingerprint("transfer", "a", "b", 100) == esperado
    assert len(esperado) == 64


def test_hash_do_pedido_e_estavel() -> None:
    primeiro = rules.request_fingerprint("transfer", "a", "b", 100)
    segundo = rules.request_fingerprint("transfer", "a", "b", 100)

    assert primeiro == segundo


@pytest.mark.parametrize(
    "outro",
    [
        ("transfer", "a", "b", 101),  # outro valor
        ("transfer", "a", "c", 100),  # outro destinatário
        ("transfer", "b", "a", 100),  # sentidos trocados
        ("transfer", "a", "b", "100"),  # o texto "100" não é o número 100
        ("trade", "a", "b", 100),  # outra operação
    ],
)
def test_pedido_diferente_tem_hash_diferente(outro: tuple[Any, ...]) -> None:
    base = rules.request_fingerprint("transfer", "a", "b", 100)

    assert rules.request_fingerprint(*outro) != base


@pytest.mark.parametrize("valor", [1, 2_500, rules.BIGINT_MAX])
def test_valor_de_transferencia_valido(valor: int) -> None:
    rules.validate_transfer_amount(valor)


@pytest.mark.parametrize("valor", [0, -1, -2_500, rules.BIGINT_MAX + 1, True, 1.5, "100", None])
def test_valor_de_transferencia_invalido_e_recusado(valor: Any) -> None:
    with pytest.raises(ValueError):
        rules.validate_transfer_amount(valor)
