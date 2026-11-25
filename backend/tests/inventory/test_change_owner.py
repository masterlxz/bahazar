"""`inventory.services.change_owner`: a única porta que troca o dono de um item (GUIDELINES 2)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from apps.inventory import selectors, services
from apps.inventory.models import SkinInstance

from .conftest import criar_instancia, criar_skin

pytestmark = pytest.mark.django_db


def test_troca_o_dono_e_preserva_id_float_skin_e_origem(ana: Any, bruno: Any, skin: Any) -> None:
    item = criar_instancia(ana, skin, "0.123456789")

    devolvido = services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    gravado = SkinInstance.objects.get(pk=item.pk)
    assert devolvido.pk == item.pk
    assert (gravado.pk, gravado.owner_id) == (item.pk, bruno.id)
    assert gravado.float_value == Decimal("0.123456789")
    assert gravado.skin_id == skin.id
    assert gravado.acquired_via == "admin_grant"
    assert gravado.acquired_at == item.acquired_at
    assert gravado.consumed_at is None
    assert SkinInstance.objects.count() == 1


def test_o_item_passa_do_inventario_de_um_para_o_do_outro(ana: Any, bruno: Any, skin: Any) -> None:
    item = criar_instancia(ana, skin)
    outro = criar_instancia(ana, skin, "0.7")

    services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    assert [i.pk for i in selectors.inventory_of(ana)] == [outro.pk]
    assert [i.pk for i in selectors.inventory_of(bruno)] == [item.pk]


def test_troca_o_dono_de_item_com_float_na_ponta_da_faixa_da_skin(ana: Any, bruno: Any) -> None:
    """O trigger do float não dispara na troca de dono, nem com o float colado na borda."""
    faixa = criar_skin("skin-faixa", minimo="0.10", maximo="0.60")
    item = criar_instancia(ana, faixa, "0.60")

    services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    assert SkinInstance.objects.get(pk=item.pk).owner_id == bruno.id


def test_recusa_quando_quem_entrega_nao_e_o_dono(
    ana: Any, bruno: Any, carla: Any, skin: Any
) -> None:
    item = criar_instancia(ana, skin)

    with pytest.raises(services.NotOwner):
        services.change_owner(item.id, from_owner=carla, to_owner=bruno)

    assert SkinInstance.objects.get(pk=item.pk).owner_id == ana.id


def test_recusa_item_que_nao_existe(ana: Any, bruno: Any) -> None:
    with pytest.raises(services.NotOwner):
        services.change_owner(uuid.uuid4(), from_owner=ana, to_owner=bruno)


def test_recusa_item_consumido_e_nao_muda_o_dono(ana: Any, bruno: Any, skin: Any) -> None:
    item = criar_instancia(ana, skin)
    SkinInstance.objects.filter(pk=item.pk).update(consumed_at=datetime.now(UTC))

    with pytest.raises(services.ConsumedInstance):
        services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    assert SkinInstance.objects.get(pk=item.pk).owner_id == ana.id


def test_os_erros_sao_de_inventario_com_codigo_estavel() -> None:
    assert issubclass(services.NotOwner, services.InventoryError)
    assert issubclass(services.ConsumedInstance, services.InventoryError)
    assert services.NotOwner.code == "not_owner"
    assert services.ConsumedInstance.code == "consumed_instance"
