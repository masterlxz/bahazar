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


# --- guardas de movimentação (I-6): um módulo pode travar o item, o núcleo não o conhece ---


def _item_locked() -> Any:
    return services.ItemLocked


def _registrar(guarda: Any) -> None:
    services.register_move_guard(guarda)


@pytest.fixture
def guardas_isoladas() -> Any:
    """Devolve o registro de guardas ao que era: a guarda falsa de um teste não vaza."""
    registro: list[Any] = services._MOVE_GUARDS
    salvo = list(registro)
    yield
    registro[:] = salvo


def test_itemlocked_e_erro_de_inventario_com_codigo_estavel() -> None:
    assert issubclass(_item_locked(), services.InventoryError)
    assert _item_locked().code == "item_locked"


def test_guarda_que_trava_impede_a_troca_de_dono(
    ana: Any, bruno: Any, skin: Any, guardas_isoladas: Any
) -> None:
    item = criar_instancia(ana, skin)

    def trava(instancia: Any, authorized_by: Any) -> None:
        raise _item_locked()

    _registrar(trava)

    with pytest.raises(_item_locked()):
        services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    assert SkinInstance.objects.get(pk=item.pk).owner_id == ana.id


def test_guarda_recebe_a_instancia_e_o_authorized_by(
    ana: Any, bruno: Any, skin: Any, guardas_isoladas: Any
) -> None:
    """Que a guarda roda SOB a trava da linha é provado em `tests/trades/test_trades_guard.py`."""
    item = criar_instancia(ana, skin)
    chamadas: list[tuple[Any, Any]] = []

    def espia(instancia: Any, authorized_by: Any) -> None:
        chamadas.append((instancia.pk, authorized_by))

    _registrar(espia)
    cracha = uuid.uuid4()
    mover: Any = services.change_owner

    mover(item.id, from_owner=ana, to_owner=bruno, authorized_by=cracha)
    mover(criar_instancia(ana, skin, "0.7").id, from_owner=ana, to_owner=bruno)

    assert chamadas[0] == (item.pk, cracha)
    assert chamadas[1][1] is None  # sem `authorized_by`, a guarda recebe None


@pytest.mark.parametrize("motivo", ["dono_errado", "inexistente", "consumido"])
def test_dono_errado_inexistente_e_consumido_vencem_a_guarda(
    ana: Any, bruno: Any, carla: Any, skin: Any, motivo: str, guardas_isoladas: Any
) -> None:
    """A guarda não roda antes: `item_locked` revelaria a um não dono que o item está em oferta."""
    item = criar_instancia(ana, skin)
    if motivo == "consumido":
        SkinInstance.objects.filter(pk=item.pk).update(consumed_at=datetime(2026, 1, 1, tzinfo=UTC))
    chamadas: list[int] = []

    def trava(instancia: Any, authorized_by: Any) -> None:
        chamadas.append(1)
        raise _item_locked()

    _registrar(trava)
    esperado = {
        "dono_errado": services.NotOwner,
        "inexistente": services.NotOwner,
        "consumido": services.ConsumedInstance,
    }[motivo]
    alvo = uuid.uuid4() if motivo == "inexistente" else item.id
    quem = carla if motivo == "dono_errado" else ana

    with pytest.raises(esperado):
        services.change_owner(alvo, from_owner=quem, to_owner=bruno)

    assert chamadas == []


def test_a_mesma_guarda_registrada_duas_vezes_roda_uma_vez(
    ana: Any, bruno: Any, skin: Any, guardas_isoladas: Any
) -> None:
    item = criar_instancia(ana, skin)
    chamadas: list[int] = []

    def conta(instancia: Any, authorized_by: Any) -> None:
        chamadas.append(1)

    _registrar(conta)
    _registrar(conta)

    services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    assert chamadas == [1]


def test_todas_as_guardas_rodam_e_a_primeira_que_trava_desfaz_a_troca(
    ana: Any, bruno: Any, skin: Any, guardas_isoladas: Any
) -> None:
    item = criar_instancia(ana, skin)
    ordem: list[str] = []

    def livre(instancia: Any, authorized_by: Any) -> None:
        ordem.append("livre")

    def trava(instancia: Any, authorized_by: Any) -> None:
        ordem.append("trava")
        raise _item_locked()

    _registrar(livre)
    _registrar(trava)

    with pytest.raises(_item_locked()):
        services.change_owner(item.id, from_owner=ana, to_owner=bruno)

    assert ordem == ["livre", "trava"]
    assert SkinInstance.objects.get(pk=item.pk).owner_id == ana.id
