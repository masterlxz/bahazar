"""Regras puras do inventário: sem banco. O desgaste é DERIVADO do float, nunca guardado.

Os cortes (0,07 / 0,15 / 0,38 / 0,45) vêm do MODELO-DE-DADOS (linha do `skin_instances`). O limite
inferior ser inclusivo (0,07 já é Minimal Wear) é hipótese do projeto, não lida na fonte da Valve.
"""

from decimal import Decimal

import pytest
from apps.inventory import rules

ORDEM = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]


@pytest.mark.parametrize(
    ("valor", "desgaste"),
    [
        ("0", "Factory New"),
        ("0.0699", "Factory New"),
        ("0.069999999", "Factory New"),
        ("0.07", "Minimal Wear"),
        ("0.1499", "Minimal Wear"),
        ("0.15", "Field-Tested"),
        ("0.3799", "Field-Tested"),
        ("0.38", "Well-Worn"),
        ("0.4499", "Well-Worn"),
        ("0.45", "Battle-Scarred"),
        ("0.9", "Battle-Scarred"),
        ("1", "Battle-Scarred"),
    ],
)
def test_desgaste_pelo_float(valor: str, desgaste: str) -> None:
    assert rules.wear_for(Decimal(valor)) == desgaste


@pytest.mark.parametrize("valor", ["-0.000000001", "1.000000001", "2", "-1"])
def test_float_fora_de_zero_a_um_e_recusado(valor: str) -> None:
    with pytest.raises(ValueError):
        rules.wear_for(Decimal(valor))


def test_varredura_de_0_a_1_cobre_todo_float_e_so_troca_nos_cortes() -> None:
    """Sem buraco e sem sobreposição: o desgaste só avança, e cada um começa no corte certo."""
    anterior = -1
    primeiro_de_cada: dict[str, Decimal] = {}
    for i in range(1001):
        f = Decimal(i) / 1000
        desgaste = rules.wear_for(f)
        posicao = ORDEM.index(desgaste)
        assert posicao >= anterior  # nunca volta para um desgaste mais novo
        anterior = posicao
        primeiro_de_cada.setdefault(desgaste, f)

    assert primeiro_de_cada == {
        "Factory New": Decimal("0"),
        "Minimal Wear": Decimal("0.07"),
        "Field-Tested": Decimal("0.15"),
        "Well-Worn": Decimal("0.38"),
        "Battle-Scarred": Decimal("0.45"),
    }


@pytest.mark.parametrize(
    ("minimo", "maximo", "unidade", "esperado"),
    [
        ("0.06", "0.80", "0", "0.06"),
        ("0.06", "0.80", "1", "0.80"),
        ("0.06", "0.80", "0.5", "0.43"),
        ("0", "1", "0.25", "0.25"),
    ],
)
def test_sorteio_do_float_respeita_a_faixa_da_skin(
    minimo: str, maximo: str, unidade: str, esperado: str
) -> None:
    resultado = rules.draw_float(Decimal(minimo), Decimal(maximo), Decimal(unidade))

    assert resultado == Decimal(esperado)


def test_sorteio_nunca_sai_da_faixa_em_nenhum_ponto_do_sorteio() -> None:
    minimo, maximo = Decimal("0.06"), Decimal("0.80")
    for i in range(1001):
        f = rules.draw_float(minimo, maximo, Decimal(i) / 1000)
        assert minimo <= f <= maximo


def test_sorteio_tem_no_maximo_9_casas_decimais() -> None:
    f = rules.draw_float(Decimal("0"), Decimal("1"), Decimal("0.123456789123456789"))

    assert f == f.quantize(Decimal("0.000000001"))


@pytest.mark.parametrize("unidade", ["-0.01", "1.01"])
def test_sorteio_recusa_unidade_fora_de_zero_a_um(unidade: str) -> None:
    with pytest.raises(ValueError):
        rules.draw_float(Decimal("0"), Decimal("1"), Decimal(unidade))


@pytest.mark.parametrize(
    ("valor", "dentro"),
    [
        ("0.06", True),  # exatamente o mínimo
        ("0.80", True),  # exatamente o máximo
        ("0.50", True),
        ("0.059999999", False),
        ("0.800000001", False),
    ],
)
def test_float_dentro_da_faixa_da_skin(valor: str, dentro: bool) -> None:
    assert rules.float_in_range(Decimal(valor), Decimal("0.06"), Decimal("0.80")) is dentro
