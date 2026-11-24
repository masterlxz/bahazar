"""Regras puras do inventário: sem Django e sem I/O, testáveis sem banco.

O float de uma skin é sempre `Decimal` (9 casas, como no banco). O desgaste NÃO é guardado:
é derivado do float por `wear_for`, para nunca existir "float 0,50 com rótulo Factory New".
"""

from decimal import Decimal

FLOAT_STEP = Decimal("0.000000001")  # 9 casas decimais, como `float_value` no banco

# Cortes do MODELO-DE-DADOS (linha do `skin_instances`). Cada desgaste vai até o limite
# EXCLUSIVO; o último (Battle-Scarred) vai até 1, inclusive. Limite inferior inclusivo é hipótese
# do projeto, não lida na fonte da Valve.
_WEAR_CUTS = (
    ("Factory New", Decimal("0.07")),
    ("Minimal Wear", Decimal("0.15")),
    ("Field-Tested", Decimal("0.38")),
    ("Well-Worn", Decimal("0.45")),
)
_LAST_WEAR = "Battle-Scarred"

# Do mais novo ao mais usado. Os rótulos que os filtros e a API aceitam.
WEARS = (*(wear for wear, _ in _WEAR_CUTS), _LAST_WEAR)

_ZERO = Decimal(0)
_ONE = Decimal(1)


def float_in_range(value: Decimal, minimum: Decimal, maximum: Decimal) -> bool:
    """O float está na faixa `[minimum, maximum]` (pontas incluídas)? Não finito nunca está."""
    return value.is_finite() and minimum <= value <= maximum


def wear_for(float_value: Decimal) -> str:
    """O desgaste de um float entre 0 e 1."""
    if not float_in_range(float_value, _ZERO, _ONE):
        raise ValueError(f"float fora de 0 a 1: {float_value}")
    for wear, upper in _WEAR_CUTS:
        if float_value < upper:
            return wear
    return _LAST_WEAR


def wear_range(wear: str) -> tuple[Decimal, Decimal]:
    """A faixa semiaberta `[início, fim)` de float de um desgaste.

    Vem da MESMA tabela de cortes de `wear_for`, para o filtro nunca discordar do rótulo. O fim
    do último desgaste é 1 + um passo, para o float 1 (que o banco aceita) entrar na faixa.
    """
    inicio = _ZERO
    for nome, fim in _WEAR_CUTS:
        if nome == wear:
            return inicio, fim
        inicio = fim
    if wear == _LAST_WEAR:
        return inicio, _ONE + FLOAT_STEP
    raise ValueError(f"desgaste desconhecido: {wear}")


def draw_float(minimum: Decimal, maximum: Decimal, unit: Decimal) -> Decimal:
    """O float na posição `unit` (0 a 1) da faixa da skin: 0 dá o mínimo, 1 dá o máximo.

    `unit` vem de fora (o sorteio fica com quem chama), para a regra ser testável sem acaso.
    """
    if not float_in_range(unit, _ZERO, _ONE):
        raise ValueError(f"unit fora de 0 a 1: {unit}")
    return (minimum + unit * (maximum - minimum)).quantize(FLOAT_STEP)
