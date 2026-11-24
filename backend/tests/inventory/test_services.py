"""`inventory.services.create_instance`: a única porta de escrita de itens (GUIDELINES 2)."""

import uuid
from decimal import Decimal
from typing import Any

import pytest

from .conftest import criar_skin

pytestmark = pytest.mark.django_db


def _criar(dono: Any, skin: Any, valor: str, **extra: Any) -> Any:
    from apps.inventory.services import create_instance

    return create_instance(
        dono, skin, Decimal(valor), acquired_via=extra.pop("acquired_via", "admin_grant"), **extra
    )


def _quantas() -> int:
    from apps.inventory.models import SkinInstance

    return SkinInstance.objects.count()


def test_cria_a_instancia_com_dono_float_e_origem(ana: Any, skin: Any) -> None:
    i = _criar(ana, skin, "0.123456789")

    assert (i.owner_id, i.skin_id) == (ana.id, skin.id)
    assert i.float_value == Decimal("0.123456789")
    assert i.acquired_via == "admin_grant"
    assert _quantas() == 1


def test_guarda_a_referencia_de_origem(ana: Any, skin: Any) -> None:
    ref = uuid.uuid4()

    assert _criar(ana, skin, "0.5", ref_id=ref).acquired_ref_id == ref


@pytest.mark.parametrize("valor", ["0.10", "0.60"])
def test_aceita_o_float_exatamente_nas_pontas_da_faixa(ana: Any, valor: str) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    assert _criar(ana, faixa, valor).float_value == Decimal(valor)


@pytest.mark.parametrize("valor", ["0.09", "0.61", "-0.1", "1.5"])
def test_float_fora_da_faixa_da_skin_e_recusado_e_nada_e_criado(ana: Any, valor: str) -> None:
    from apps.inventory.services import InvalidFloat

    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    with pytest.raises(InvalidFloat) as erro:
        _criar(ana, faixa, valor)

    assert erro.value.code == "invalid_float"
    assert _quantas() == 0


def test_skin_inativa_nao_e_dada_a_ninguem(ana: Any) -> None:
    from apps.inventory.services import InactiveSkin

    inativa = criar_skin("skin-velha", ativa=False)

    with pytest.raises(InactiveSkin) as erro:
        _criar(ana, inativa, "0.5")

    assert erro.value.code == "inactive_skin"
    assert _quantas() == 0


def test_origem_desconhecida_e_recusada(ana: Any, skin: Any) -> None:
    from apps.inventory.services import InventoryError

    with pytest.raises(InventoryError):
        _criar(ana, skin, "0.5", acquired_via="inventada")

    assert _quantas() == 0
