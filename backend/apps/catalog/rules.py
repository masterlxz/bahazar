"""Regras puras do catálogo: sem Django e sem I/O, testáveis sem banco."""

from collections.abc import Iterable
from decimal import ROUND_DOWN, Decimal

# Teto de sanidade do preço de uma skin: US$ 100 milhões. Só impede um valor absurdo de estourar
# o bigint; o maior preço de uma skin comum medido na PR 3.0 foi de US$ 13.683.
MAX_REFERENCE_PRICE_CENTS = 10_000_000_000

# Do desgaste mais comum no mercado para o menos comum: o preço de referência de uma skin é o do
# primeiro destes que ela tem.
WEAR_PREFERENCE = (
    "Field-Tested",
    "Minimal Wear",
    "Well-Worn",
    "Battle-Scarred",
    "Factory New",
)

# Facas e luvas (★), StatTrak™ e Souvenir ficam fora do catálogo desta fase.
_EXCLUDED_PREFIXES = ("★", "StatTrak™", "Souvenir")


def usd_to_cents(usd: Decimal) -> int:
    """Dólares em centavos inteiros, metade para cima. Único ponto de conversão de preço.

    Recebe `Decimal` de propósito: um `float` já chega impreciso (1.005 vira 1.00499...).
    """
    if not usd.is_finite():
        raise ValueError(f"preço não é um número finito: {usd}")
    # Os limites vêm antes da conta: um expoente enorme estouraria a precisão do quantize.
    if usd <= 0:
        raise ValueError(f"preço precisa ser de ao menos 1 centavo: {usd}")
    if usd > Decimal(MAX_REFERENCE_PRICE_CENTS) / 100:
        raise ValueError(f"preço acima do teto: {usd}")
    cents = (usd * 100).quantize(Decimal(1), rounding=ROUND_DOWN)
    if cents <= 0:
        raise ValueError(f"preço precisa ser de ao menos 1 centavo: {usd}")
    return int(cents)


def reference_wear(wears: Iterable[str]) -> str | None:
    """O desgaste cujo preço representa a skin, entre os que ela tem; `None` se nenhum serve."""
    disponiveis = set(wears)
    for wear in WEAR_PREFERENCE:
        if wear in disponiveis:
            return wear
    return None


def is_importable_name(name: str) -> bool:
    return not name.startswith(_EXCLUDED_PREFIXES)


def market_name(name: str, wear: str) -> str:
    """O nome do item no mercado: `AK-47 | Redline (Field-Tested)`."""
    return f"{name} ({wear})"
