"""A divisão do preço entre vendedor e taxa: regra pura, sem banco (ADR 0018).

A taxa de 5% é uma HIPÓTESE do dono (2026-11-26), não um valor medido; arredonda para baixo.
Aqui a conta é independente da constante: 5% de `p` é `p // 20`, exato.
"""

import pytest

from apps.marketplace import rules

MAX_PRICE = 2**53 - 1


@pytest.mark.parametrize(
    ("preco", "vendedor", "taxa"),
    [
        (1, 1, 0),
        (19, 19, 0),
        (20, 19, 1),
        (21, 20, 1),
        (39, 38, 1),
        (40, 38, 2),
        (1000, 950, 50),
    ],
)
def test_a_taxa_e_5_por_cento_arredondada_para_baixo(preco: int, vendedor: int, taxa: int) -> None:
    assert rules.split_price(preco) == (vendedor, taxa)


@pytest.mark.parametrize("preco", [1, 2, 19, 20, 21, 99, 100, 12_345, 10**12, MAX_PRICE])
def test_a_divisao_soma_o_preco_e_o_vendedor_nunca_recebe_zero(preco: int) -> None:
    vendedor, taxa = rules.split_price(preco)

    assert vendedor + taxa == preco
    assert taxa == preco // 20
    assert vendedor >= 1


@pytest.mark.parametrize("preco", [0, -1, -1000])
def test_preco_que_nao_e_positivo_e_recusado(preco: int) -> None:
    with pytest.raises(ValueError):
        rules.split_price(preco)
