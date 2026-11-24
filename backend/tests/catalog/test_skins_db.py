"""Garantias do banco para `skins`: valem mesmo que o import ou um serviço tenham bug."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def _skin(**campos: Any) -> Any:
    from apps.catalog.models import Skin

    base: dict[str, Any] = {
        "external_id": "skin-1",
        "weapon": "AK-47",
        "name": "AK-47 | Teste",
        "collection": "Coleção Teste",
        "rarity": "Classified",
        "min_float": Decimal("0"),
        "max_float": Decimal("1"),
        "reference_price": 1234,
    }
    base.update(campos)
    return Skin.objects.create(**base)


def test_skin_valida_e_criada_com_os_padroes() -> None:
    s = _skin()

    assert s.active is True
    assert s.image_url == ""
    assert s.image_source == "none"
    assert s.reference_price == 1234


def test_banco_recusa_external_id_repetido() -> None:
    _skin()

    with pytest.raises(IntegrityError), transaction.atomic():
        _skin(name="Outra")


@pytest.mark.parametrize("preco", [0, -1])
def test_banco_recusa_preco_de_referencia_nao_positivo(preco: int) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _skin(reference_price=preco)


def test_banco_aceita_preco_de_um_centavo() -> None:
    assert _skin(reference_price=1).reference_price == 1


@pytest.mark.parametrize(
    ("minimo", "maximo"),
    [
        ("0.5", "0.5"),  # min == max
        ("0.8", "0.2"),  # min > max
        ("-0.1", "0.5"),  # abaixo de 0
        ("0", "1.1"),  # acima de 1
    ],
)
def test_banco_recusa_faixa_de_float_invalida(minimo: str, maximo: str) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _skin(min_float=Decimal(minimo), max_float=Decimal(maximo))


def test_banco_aceita_a_faixa_completa_de_zero_a_um() -> None:
    s = _skin(min_float=Decimal("0"), max_float=Decimal("1"))

    assert s.min_float == 0
    assert s.max_float == 1
