"""API do inventário: o meu, e a forma dos itens (PR 3.2b). Só leitura."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from .conftest import INVENTORY_URL, criar_instancia, criar_skin, logado, url_de

pytestmark = pytest.mark.django_db

CAMPOS_ITEM = {"id", "skin", "float_value", "wear", "reference_price", "acquired_at"}
CAMPOS_SKIN = {"id", "name", "weapon", "rarity", "collection"}


def _ids(resposta: Any) -> list[str]:
    return [item["id"] for item in resposta.json()["results"]]


def test_anonimo_nao_ve_inventario_nenhum() -> None:
    assert APIClient().get(INVENTORY_URL).status_code in (401, 403)
    assert APIClient().get(url_de("ana_01")).status_code in (401, 403)


def test_jogador_sem_itens_recebe_lista_vazia(ana: Any) -> None:
    resposta = logado(ana).get(INVENTORY_URL)

    assert resposta.status_code == 200
    assert resposta.json()["count"] == 0
    assert resposta.json()["results"] == []


def test_o_inventario_mostra_so_os_itens_do_dono(ana: Any, bruno: Any, skin: Any) -> None:
    meu1 = criar_instancia(ana, skin)
    meu2 = criar_instancia(ana, skin)
    criar_instancia(bruno, skin)

    resposta = logado(ana).get(INVENTORY_URL)

    assert sorted(_ids(resposta)) == sorted([str(meu1.id), str(meu2.id)])


def test_item_consumido_sai_do_inventario(ana: Any, skin: Any) -> None:
    from apps.inventory.models import SkinInstance

    fica = criar_instancia(ana, skin)
    some = criar_instancia(ana, skin)
    SkinInstance.objects.filter(pk=some.pk).update(consumed_at=datetime(2026, 11, 24, tzinfo=UTC))

    assert _ids(logado(ana).get(INVENTORY_URL)) == [str(fica.id)]


def test_item_de_skin_que_ficou_inativa_continua_no_inventario(ana: Any, skin: Any) -> None:
    item = criar_instancia(ana, skin)
    skin.active = False
    skin.save()

    assert _ids(logado(ana).get(INVENTORY_URL)) == [str(item.id)]


def test_o_item_traz_so_os_campos_do_contrato(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin)

    item = logado(ana).get(INVENTORY_URL).json()["results"][0]

    assert set(item) == CAMPOS_ITEM
    assert set(item["skin"]) == CAMPOS_SKIN
    for proibido in ("acquired_via", "acquired_ref_id", "consumed_at", "owner", "owner_id"):
        assert proibido not in item


def test_float_vem_como_texto_o_desgaste_e_derivado_e_o_preco_e_inteiro(ana: Any) -> None:
    caro = criar_skin("skin-caro", preco=2500)
    criar_instancia(ana, caro, "0.07")

    item = logado(ana).get(INVENTORY_URL).json()["results"][0]

    assert isinstance(item["float_value"], str)
    assert Decimal(item["float_value"]) == Decimal("0.07")
    assert item["wear"] == "Minimal Wear"
    assert item["reference_price"] == 2500
    assert isinstance(item["reference_price"], int)
    assert item["skin"]["id"] == str(caro.id)
    assert item["skin"]["name"] == caro.name


def test_a_lista_e_paginada_com_24_por_pagina(ana: Any, skin: Any) -> None:
    for _ in range(30):
        criar_instancia(ana, skin)

    corpo = logado(ana).get(INVENTORY_URL).json()

    assert set(corpo) == {"count", "next", "previous", "results"}
    assert corpo["count"] == 30
    assert len(corpo["results"]) == 24
    assert corpo["next"] is not None
    assert corpo["previous"] is None


def test_pagina_alem_do_fim_da_404(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin)

    assert logado(ana).get(INVENTORY_URL, {"page": 2}).status_code == 404


def test_a_ordem_padrao_e_do_mais_novo_para_o_mais_antigo(ana: Any, skin: Any) -> None:
    from apps.inventory.models import SkinInstance

    antigo = criar_instancia(ana, skin)
    novo = criar_instancia(ana, skin)
    SkinInstance.objects.filter(pk=antigo.pk).update(acquired_at=datetime(2026, 1, 1, tzinfo=UTC))
    SkinInstance.objects.filter(pk=novo.pk).update(acquired_at=datetime(2026, 6, 1, tzinfo=UTC))

    assert _ids(logado(ana).get(INVENTORY_URL)) == [str(novo.id), str(antigo.id)]


def test_o_proprio_username_na_rota_mostra_o_mesmo_inventario(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin)

    cliente = logado(ana)

    assert _ids(cliente.get(url_de("ana_01"))) == _ids(cliente.get(INVENTORY_URL))
    assert cliente.get(url_de("ana_01")).status_code == 200


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_a_api_do_inventario_so_le(ana: Any, bruno: Any, metodo: str) -> None:
    cliente = logado(ana)

    assert getattr(cliente, metodo)(INVENTORY_URL, {}, format="json").status_code == 405
    assert getattr(cliente, metodo)(url_de("bruno_02"), {}, format="json").status_code == 405
