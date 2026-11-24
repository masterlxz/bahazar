"""Comando administrativo `grant_skin`: dá uma skin a um jogador (PR 3.2a, sem API)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from .conftest import criar_skin

pytestmark = pytest.mark.django_db


def _instancias() -> Any:
    from apps.inventory.models import SkinInstance

    return SkinInstance.objects


def test_da_a_skin_ao_jogador_com_float_dentro_da_faixa(ana: Any, capsys: Any) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    call_command("grant_skin", user=ana.username, skin=faixa.external_id)

    i = _instancias().get()
    assert (i.owner_id, i.skin_id, i.acquired_via) == (ana.id, faixa.id, "admin_grant")
    assert Decimal("0.10") <= i.float_value <= Decimal("0.60")
    assert str(i.id) in capsys.readouterr().out


def test_o_float_sorteado_nunca_sai_da_faixa(ana: Any) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    for _ in range(25):
        call_command("grant_skin", user=ana.username, skin=faixa.external_id)

    valores = list(_instancias().values_list("float_value", flat=True))
    assert len(valores) == 25
    assert all(Decimal("0.10") <= v <= Decimal("0.60") for v in valores)


def test_float_informado_e_usado_exatamente(ana: Any, skin: Any) -> None:
    call_command("grant_skin", user=ana.username, skin=skin.external_id, float="0.123456789")

    assert _instancias().get().float_value == Decimal("0.123456789")


@pytest.mark.parametrize("valor", ["0.09", "0.61", "abc", "NaN"])
def test_float_invalido_ou_fora_da_faixa_sai_com_erro_e_nada_e_criado(ana: Any, valor: str) -> None:
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")

    with pytest.raises(CommandError):
        call_command("grant_skin", user=ana.username, skin=faixa.external_id, float=valor)

    assert _instancias().count() == 0


def test_jogador_inexistente_sai_com_erro(skin: Any) -> None:
    with pytest.raises(CommandError):
        call_command("grant_skin", user="ninguem", skin=skin.external_id)

    assert _instancias().count() == 0


def test_skin_inexistente_sai_com_erro(ana: Any) -> None:
    with pytest.raises(CommandError):
        call_command("grant_skin", user=ana.username, skin="skin-que-nao-existe")

    assert _instancias().count() == 0


def test_skin_inativa_sai_com_erro(ana: Any) -> None:
    inativa = criar_skin("skin-velha", ativa=False)

    with pytest.raises(CommandError):
        call_command("grant_skin", user=ana.username, skin=inativa.external_id)

    assert _instancias().count() == 0
