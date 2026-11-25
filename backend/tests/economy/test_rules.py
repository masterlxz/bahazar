"""Regras puras da economia (sem banco): valores da D7, diária em sequência e validação.

Os valores esperados vêm da decisão do dono (2026-11-25, ADR 0013 e SIMULACAO-4.0-ECONOMIA.md):
saldo inicial US$ 25,00, diária de US$ 2,50 por dia da sequência até o dia 14 (US$ 35,00).
"""

from datetime import timedelta

import pytest

from apps.economy import rules

H = timedelta(hours=1)


def test_saldo_inicial_e_25_dolares_em_centavos() -> None:
    assert rules.STARTING_BALANCE == 2_500


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [(1, 250), (2, 500), (3, 750), (13, 3_250), (14, 3_500), (15, 3_500), (45, 3_500)],
)
def test_diaria_cresce_2_dolares_e_meio_por_dia_ate_o_teto_do_dia_14(
    dia: int, esperado: int
) -> None:
    assert rules.daily_amount(dia) == esperado


@pytest.mark.parametrize("dia", [0, -1])
def test_dia_da_sequencia_invalido_e_rejeitado(dia: int) -> None:
    with pytest.raises(ValueError):
        rules.daily_amount(dia)


def test_primeiro_resgate_esta_liberado() -> None:
    assert rules.can_claim(None) is True


@pytest.mark.parametrize(
    ("decorrido", "liberado"),
    [
        (timedelta(0), False),
        (24 * H - timedelta(seconds=1), False),
        (24 * H, True),
        (100 * H, True),
    ],
)
def test_resgate_so_libera_24h_depois_do_ultimo(decorrido: timedelta, liberado: bool) -> None:
    assert rules.can_claim(decorrido) is liberado


@pytest.mark.parametrize(
    ("anterior", "decorrido", "esperado"),
    [
        (None, None, 1),
        (1, 24 * H, 2),
        (2, 47 * H + timedelta(minutes=59, seconds=59), 3),
        (1, 48 * H, 1),
        (5, 100 * 24 * H, 1),
        (30, 25 * H, 31),
    ],
)
def test_sequencia_continua_entre_24h_e_48h_e_zera_depois(
    anterior: int | None, decorrido: timedelta | None, esperado: int
) -> None:
    assert rules.next_streak_day(anterior, decorrido) == esperado


def test_lancamento_que_soma_zero_e_valido() -> None:
    rules.validate_entries([-500, 500])
    rules.validate_entries([-100, 90, 10])


@pytest.mark.parametrize(
    "valores",
    [
        [-100, 50],  # não soma zero
        [100],  # uma linha só
        [],  # vazio
        [0, 0],  # valores nulos
        [-1.5, 1.5],  # não inteiro
        [-(2**63) - 1, 2**63 + 1],  # fora do bigint
        [True, -1],  # bool não é dinheiro
    ],
)
def test_lancamento_invalido_e_rejeitado(valores: list[object]) -> None:
    with pytest.raises(ValueError):
        rules.validate_entries(valores)  # type: ignore[arg-type]
