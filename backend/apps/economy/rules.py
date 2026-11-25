"""Regras puras da economia: sem Django e sem I/O, testáveis sem banco.

Unidade de dinheiro: **1 centavo de dólar** (ADR 0011). Saldo inicial e diária foram decididos
pelo dono em 2026-11-25 a partir da simulação da PR 4.0 (ADR 0013, RISCOS D7); o valor do anúncio
segue em aberto (teto: ~10% da diária de regime).
"""

from collections.abc import Sequence
from datetime import timedelta

STARTING_BALANCE = 2_500  # US$ 25,00
DAILY_STEP = 250  # US$ 2,50 por dia de sequência
DAILY_CAP_DAY = 14  # a diária para de crescer no dia 14 (US$ 35,00)
DAILY_WINDOW = timedelta(hours=24)  # a diária só libera 24h depois do último resgate
STREAK_BREAK = timedelta(hours=48)  # 48h ou mais sem resgatar zera a sequência

BIGINT_MAX = 2**63 - 1
BIGINT_MIN = -(2**63)


def daily_amount(streak_day: int) -> int:
    """Valor da diária no dia `streak_day` da sequência (1 = primeiro dia)."""
    if streak_day < 1:
        raise ValueError("o dia da sequência começa em 1")
    return DAILY_STEP * min(streak_day, DAILY_CAP_DAY)


def can_claim(elapsed: timedelta | None) -> bool:
    """`elapsed` é o tempo desde o último resgate (None = nunca resgatou)."""
    return elapsed is None or elapsed >= DAILY_WINDOW


def next_streak_day(previous: int | None, elapsed: timedelta | None) -> int:
    """Dia da sequência do próximo resgate: continua entre 24h e 48h, senão volta ao 1."""
    if previous is None or elapsed is None or elapsed >= STREAK_BREAK:
        return 1
    return previous + 1


def normalize_idempotency_key(key: str) -> str:
    # ESBOÇO INGÊNUO do commit só de testes: não valida nem normaliza nada.
    return key


def request_fingerprint(*parts: object) -> str:
    # ESBOÇO INGÊNUO do commit só de testes: o mesmo hash para qualquer pedido.
    return "0" * 64


def validate_transfer_amount(amount: int) -> None:
    # ESBOÇO INGÊNUO do commit só de testes: aceita qualquer valor.
    return None


def validate_entries(amounts: Sequence[int]) -> None:
    """Um lançamento de partida dobrada: 2+ linhas, inteiros não nulos no `bigint`, soma zero."""
    if len(amounts) < 2:
        raise ValueError("um lançamento precisa de pelo menos duas linhas")
    for valor in amounts:
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError(f"valor não inteiro: {valor!r}")
        if valor == 0:
            raise ValueError("valor nulo não é permitido")
        if not BIGINT_MIN <= valor <= BIGINT_MAX:
            raise ValueError("valor fora do intervalo de bigint")
    if sum(amounts) != 0:
        raise ValueError(f"o lançamento não soma zero (soma = {sum(amounts)})")
