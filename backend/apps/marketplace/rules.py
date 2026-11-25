"""Regras puras do mercado: estados dos anúncios e limites do preço, sem Django e sem I/O."""

ACTIVE = "active"
SOLD = "sold"
CANCELLED = "cancelled"

MIN_PRICE = 1
MAX_PRICE = 2**63 - 1


def price_is_valid(value: object) -> bool:
    """O preço é um inteiro de centavos dentro do alcance de um bigint do PostgreSQL?"""
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return MIN_PRICE <= value <= MAX_PRICE
