"""Regras puras do mercado: estados dos anúncios e limites do preço, sem Django e sem I/O."""

ACTIVE = "active"
SOLD = "sold"
CANCELLED = "cancelled"

MIN_PRICE = 1
# O maior inteiro que o JavaScript do frontend representa sem arredondar (MAX_SAFE_INTEGER).
# Acima disso a tela mostraria um preço diferente do gravado. Cabe com folga no bigint do banco.
# Não é regra de negócio (decisão do dono, 2026-11-26); um teto de produto fica para a 4.4.
MAX_PRICE = 2**63 - 1


def price_is_valid(value: object) -> bool:
    """O preço é um inteiro de centavos entre `MIN_PRICE` e `MAX_PRICE`?"""
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return MIN_PRICE <= value <= MAX_PRICE
