"""Regras puras do mercado: estados dos anúncios e limites do preço, sem Django e sem I/O."""

ACTIVE = "active"
SOLD = "sold"
CANCELLED = "cancelled"

MIN_PRICE = 1
# O maior inteiro que o JavaScript do frontend representa sem arredondar (MAX_SAFE_INTEGER).
# Acima disso a tela mostraria um preço diferente do gravado. Cabe com folga no bigint do banco.
# Não é regra de negócio (decisão do dono, 2026-11-26); um teto de produto fica para a 4.4.
MAX_PRICE = 2**53 - 1


# Taxa do mercado, em basis points (500 = 5%). HIPÓTESE do dono (2026-11-26), não medida: vem da
# simulação 4.0 (ADR 0013); reabrir com dados reais. É o sumidouro que queima a renda de regime.
MARKET_FEE_BPS = 500
_BPS = 10_000


def split_price(price: int) -> tuple[int, int]:
    """Divide o preço de uma compra em `(para_o_vendedor, taxa)`, em centavos.

    A taxa arredonda para baixo (`price * bps // 10_000`), então o vendedor recebe `price - taxa`
    e nunca zero (a taxa é sempre menor que o preço); preço até 19 centavos paga taxa 0. O preço
    inválido levanta `ValueError`: quem chama já o validou na criação do anúncio.
    """
    if not price_is_valid(price):
        raise ValueError("o preço precisa ser um inteiro positivo dentro do limite")
    taxa = price * MARKET_FEE_BPS // _BPS
    return price - taxa, taxa


def price_is_valid(value: object) -> bool:
    """O preço é um inteiro de centavos entre `MIN_PRICE` e `MAX_PRICE`?"""
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return MIN_PRICE <= value <= MAX_PRICE
