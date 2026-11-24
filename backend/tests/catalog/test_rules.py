"""Regras puras do catálogo: sem banco. Dinheiro vira inteiro em UM lugar, sem float."""

from decimal import Decimal

import pytest

from apps.catalog import rules

TODOS = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]


@pytest.mark.parametrize(
    ("usd", "centavos"),
    [
        ("12.34", 1234),
        ("0.01", 1),
        ("2.13", 213),
        ("173884.79", 17388479),
        ("0.005", 1),  # metade sobe
        ("0.014", 1),
        ("0.015", 2),
        ("1.005", 101),  # em float seria 100.49999999999999 e daria 100
    ],
)
def test_dolar_vira_centavos_inteiros(usd: str, centavos: int) -> None:
    resultado = rules.usd_to_cents(Decimal(usd))

    assert resultado == centavos
    assert isinstance(resultado, int)


@pytest.mark.parametrize("usd", ["0", "0.004", "-1", "-0.01", "NaN", "Infinity", "-Infinity"])
def test_preco_invalido_e_recusado(usd: str) -> None:
    with pytest.raises(ValueError):
        rules.usd_to_cents(Decimal(usd))


def test_o_teto_do_preco_e_aceito_e_acima_dele_recusado() -> None:
    teto = Decimal(rules.MAX_REFERENCE_PRICE_CENTS) / 100

    assert rules.usd_to_cents(teto) == rules.MAX_REFERENCE_PRICE_CENTS
    with pytest.raises(ValueError):
        rules.usd_to_cents(teto + Decimal("0.01"))


@pytest.mark.parametrize(
    ("desgastes", "esperado"),
    [
        (TODOS, "Field-Tested"),
        (["Factory New", "Minimal Wear", "Well-Worn", "Battle-Scarred"], "Minimal Wear"),
        (["Factory New", "Well-Worn", "Battle-Scarred"], "Well-Worn"),
        (["Factory New", "Battle-Scarred"], "Battle-Scarred"),
        (["Factory New"], "Factory New"),
        (["Battle-Scarred", "Factory New", "Field-Tested"], "Field-Tested"),  # fora de ordem
        (["Desgaste Inventado"], None),
        ([], None),
    ],
)
def test_desgaste_de_referencia(desgastes: list[str], esperado: str | None) -> None:
    assert rules.reference_wear(desgastes) == esperado


@pytest.mark.parametrize(
    ("nome", "importavel"),
    [
        ("AK-47 | Teste", True),
        ("M4A4 | Inventada", True),
        ("StatTrak™ AK-47 | Teste", False),
        ("Souvenir AWP | Teste", False),
        ("★ Faca | Teste", False),
        ("★ StatTrak™ Faca | Teste", False),
    ],
)
def test_so_skins_comuns_sao_importaveis(nome: str, importavel: bool) -> None:
    assert rules.is_importable_name(nome) is importavel


def test_o_nome_de_mercado_junta_nome_e_desgaste() -> None:
    assert rules.market_name("AK-47 | Teste", "Field-Tested") == "AK-47 | Teste (Field-Tested)"
