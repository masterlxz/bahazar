"""Guarda de `trades` sobre `change_owner` (I-6): item em oferta pendente não muda de dono.

Sem a guarda, o mercado (4.3) poderia vender um item que está numa oferta pendente: a oferta
velha ficaria presa e o índice `tradeitem_one_active_per_instance` impediria o novo dono de
oferecê-lo. O cenário (`cena`) é de `conftest.py`: ana tem a1 e a2, bruno tem b1 e b2.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance
from apps.trades import guards, services
from apps.trades.models import TradeOffer, TradeStatus

from .conftest import criar_instancia

pytestmark = pytest.mark.django_db

mover = inventory_services.change_owner


def _item_locked() -> Any:
    return inventory_services.ItemLocked


def _oferecer(cena: SimpleNamespace) -> TradeOffer:
    """ana oferece a1 e pede b1 de bruno."""
    return services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def test_a_guarda_da_troca_esta_registrada() -> None:
    """Prova o `ready()` de `trades`: sem o registro, nada trava e o resto dos testes enganaria."""
    assert guards.offer_guard in inventory_services._MOVE_GUARDS


@pytest.mark.parametrize("lado", ["oferecido", "pedido"])
def test_item_em_oferta_pendente_nao_muda_de_dono(cena: SimpleNamespace, lado: str) -> None:
    oferta = _oferecer(cena)
    item, dono = (cena.a1, cena.ana) if lado == "oferecido" else (cena.b1, cena.bruno)

    with pytest.raises(_item_locked()):
        mover(item.id, from_owner=dono, to_owner=cena.carla)

    assert _dono(item) == dono.id
    oferta.refresh_from_db()
    assert oferta.status == TradeStatus.PENDING


def test_item_que_nao_esta_em_oferta_continua_livre(cena: SimpleNamespace) -> None:
    _oferecer(cena)  # a1 e b1 ocupados; a2 e b2 não

    mover(cena.a2.id, from_owner=cena.ana, to_owner=cena.carla)

    assert _dono(cena.a2) == cena.carla.id


@pytest.mark.parametrize("fim", ["recusada", "cancelada"])
def test_oferta_resolvida_sem_troca_libera_o_item(cena: SimpleNamespace, fim: str) -> None:
    oferta = _oferecer(cena)
    if fim == "recusada":
        services.decline_offer(cena.bruno, oferta.pk)
    else:
        services.cancel_offer(cena.ana, oferta.pk)

    mover(cena.a1.id, from_owner=cena.ana, to_owner=cena.carla)

    assert _dono(cena.a1) == cena.carla.id


def test_aceitar_a_oferta_funciona_e_o_item_fica_livre_depois(cena: SimpleNamespace) -> None:
    """O aceite move itens da PRÓPRIA oferta pendente; depois, a oferta deixa de travar."""
    oferta = _oferecer(cena)

    services.accept_offer(cena.bruno, oferta.pk)

    assert _dono(cena.a1) == cena.bruno.id
    assert _dono(cena.b1) == cena.ana.id
    mover(cena.a1.id, from_owner=cena.bruno, to_owner=cena.carla)
    assert _dono(cena.a1) == cena.carla.id


def test_o_cracha_da_propria_oferta_destrava_e_o_de_outra_oferta_nao(
    cena: SimpleNamespace,
) -> None:
    oferta = _oferecer(cena)

    with pytest.raises(_item_locked()):
        mover(cena.a1.id, from_owner=cena.ana, to_owner=cena.carla, authorized_by=uuid.uuid4())
    assert _dono(cena.a1) == cena.ana.id

    mover(cena.a1.id, from_owner=cena.ana, to_owner=cena.carla, authorized_by=oferta.pk)
    assert _dono(cena.a1) == cena.carla.id


def test_o_cracha_de_uma_oferta_nao_destrava_item_de_outra(
    cena: SimpleNamespace, skin: Any
) -> None:
    """Duas ofertas pendentes: autorizar a de bruno não solta o item da oferta de ana."""
    oferta_ana = _oferecer(cena)
    c2 = criar_instancia(cena.bruno, skin, "0.4")
    oferta_bruno = services.create_offer(cena.bruno, cena.ana, [c2.id], [cena.a2.id])

    with pytest.raises(_item_locked()):
        mover(cena.a1.id, from_owner=cena.ana, to_owner=cena.carla, authorized_by=oferta_bruno.pk)

    assert oferta_ana.pk != oferta_bruno.pk
    assert _dono(cena.a1) == cena.ana.id
