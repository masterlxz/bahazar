"""Garantias do banco para `skin_instances`: valem mesmo que o serviço ou o import tenham bug."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError

from .conftest import criar_instancia, criar_skin

pytestmark = pytest.mark.django_db


def _modelo() -> Any:
    from apps.inventory.models import SkinInstance

    return SkinInstance


def test_instancia_nasce_com_data_e_sem_consumo(ana: Any, skin: Any) -> None:
    i = criar_instancia(ana, skin)

    assert i.acquired_at is not None
    assert i.acquired_ref_id is None
    assert i.consumed_at is None
    assert i.owner_id == ana.id


# --- trigger: float dentro da faixa da skin ----------------------------------------------------


@pytest.mark.parametrize("valor", ["0.09", "0.099999999", "0.61", "0.600000001"])
def test_banco_recusa_float_fora_da_faixa_da_skin(ana: Any, valor: str) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    with pytest.raises(DatabaseError, match="faixa"), transaction.atomic():
        criar_instancia(ana, faixa, valor)

    assert _modelo().objects.count() == 0


@pytest.mark.parametrize("valor", ["0.10", "0.60", "0.35"])
def test_banco_aceita_float_nas_pontas_e_dentro_da_faixa(ana: Any, valor: str) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    assert criar_instancia(ana, faixa, valor).float_value == Decimal(valor)


def test_banco_recusa_mudar_o_float_para_fora_da_faixa(ana: Any) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")
    i = criar_instancia(ana, faixa, "0.30")

    with pytest.raises(DatabaseError, match="faixa"), transaction.atomic():
        _modelo().objects.filter(pk=i.pk).update(float_value=Decimal("0.99"))

    i.refresh_from_db()
    assert i.float_value == Decimal("0.30")


def test_banco_recusa_trocar_a_skin_por_uma_cuja_faixa_nao_contem_o_float(ana: Any) -> None:
    larga = criar_skin("skin-larga", minimo="0", maximo="1")
    estreita = criar_skin("skin-estreita", minimo="0.10", maximo="0.20")
    i = criar_instancia(ana, larga, "0.50")

    with pytest.raises(DatabaseError, match="faixa"), transaction.atomic():
        _modelo().objects.filter(pk=i.pk).update(skin=estreita)


# --- CHECKs e chaves ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", ["-0.1", "1.5"])
def test_banco_recusa_float_fora_de_zero_a_um(ana: Any, skin: Any, valor: str) -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        criar_instancia(ana, skin, valor)


def test_o_check_de_zero_a_um_existe_no_modelo() -> None:
    nomes = {c.name for c in _modelo()._meta.constraints}

    assert "skininstance_float_unit_range" in nomes


def test_banco_recusa_origem_desconhecida(ana: Any, skin: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _modelo().objects.create(
            owner=ana, skin=skin, float_value=Decimal("0.5"), acquired_via="inventada"
        )


def test_banco_recusa_instancia_sem_dono(skin: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _modelo().objects.create(
            owner=None, skin=skin, float_value=Decimal("0.5"), acquired_via="admin_grant"
        )


def test_nao_se_apaga_skin_que_tem_instancia(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin)

    with pytest.raises(ProtectedError):
        skin.delete()


def test_nao_se_apaga_usuario_que_tem_instancia(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin)

    with pytest.raises(ProtectedError):
        ana.delete()


def test_o_mesmo_jogador_pode_ter_varias_copias_da_mesma_skin(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin, "0.10")
    criar_instancia(ana, skin, "0.20")

    assert _modelo().objects.filter(owner=ana, skin=skin).count() == 2
