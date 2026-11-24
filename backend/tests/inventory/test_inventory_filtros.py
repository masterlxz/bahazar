"""Filtros, ordenação e paginação do inventário (PR 3.2b)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .conftest import INVENTORY_URL, criar_instancia, criar_skin, logado

pytestmark = pytest.mark.django_db


def _ids(resposta: Any) -> list[str]:
    assert resposta.status_code == 200, resposta.content
    return [item["id"] for item in resposta.json()["results"]]


def _nomes(resposta: Any) -> list[str]:
    assert resposta.status_code == 200, resposta.content
    return [item["skin"]["name"] for item in resposta.json()["results"]]


def _floats(resposta: Any) -> list[str]:
    assert resposta.status_code == 200, resposta.content
    return [item["float_value"] for item in resposta.json()["results"]]


# --- filtros -------------------------------------------------------------------------------


def test_filtra_por_raridade_sem_diferenciar_maiuscula(ana: Any) -> None:
    raro = criar_instancia(ana, criar_skin("s-raro", raridade="Covert"))
    criar_instancia(ana, criar_skin("s-comum", raridade="Restricted"))

    assert _ids(logado(ana).get(INVENTORY_URL, {"rarity": "covert"})) == [str(raro.id)]


def test_filtra_por_arma_sem_diferenciar_maiuscula(ana: Any) -> None:
    awp = criar_instancia(ana, criar_skin("s-awp", arma="AWP"))
    criar_instancia(ana, criar_skin("s-ak", arma="AK-47"))

    assert _ids(logado(ana).get(INVENTORY_URL, {"weapon": "awp"})) == [str(awp.id)]


def test_busca_por_trecho_do_nome(ana: Any) -> None:
    ak = criar_instancia(ana, criar_skin("s-ak", nome="AK-47 | Redline"))
    criar_instancia(ana, criar_skin("s-awp", nome="AWP | Asiimov"))

    assert _ids(logado(ana).get(INVENTORY_URL, {"q": "redLINE"})) == [str(ak.id)]


@pytest.mark.parametrize(
    ("desgaste", "esperados"),
    [
        ("Factory New", ["0.000000000", "0.069999999"]),
        ("Minimal Wear", ["0.070000000", "0.149999999"]),
        ("Field-Tested", ["0.150000000"]),
        ("Well-Worn", ["0.380000000"]),
        ("Battle-Scarred", ["0.450000000", "1.000000000"]),
    ],
)
def test_filtra_por_desgaste_pelas_fronteiras_do_float(
    ana: Any, desgaste: str, esperados: list[str]
) -> None:
    skin = criar_skin()
    for valor in ["0", "0.069999999", "0.07", "0.149999999", "0.15", "0.38", "0.45", "1"]:
        criar_instancia(ana, skin, valor)

    resposta = logado(ana).get(INVENTORY_URL, {"wear": desgaste, "ordering": "float_value"})

    assert _floats(resposta) == esperados


def test_filtros_combinados_fazem_e(ana: Any) -> None:
    alvo = criar_instancia(ana, criar_skin("s-1", arma="AWP", raridade="Covert"), "0.5")
    criar_instancia(ana, criar_skin("s-2", arma="AWP", raridade="Restricted"), "0.5")
    criar_instancia(ana, criar_skin("s-3", arma="AK-47", raridade="Covert"), "0.5")
    criar_instancia(ana, criar_skin("s-4", arma="AWP", raridade="Covert"), "0.01")

    params = {"weapon": "AWP", "rarity": "Covert", "wear": "Battle-Scarred"}

    assert _ids(logado(ana).get(INVENTORY_URL, params)) == [str(alvo.id)]


# --- ordenação -----------------------------------------------------------------------------


def test_ordena_por_float(ana: Any, skin: Any) -> None:
    for valor in ["0.30", "0.10", "0.20"]:
        criar_instancia(ana, skin, valor)
    cliente = logado(ana)

    assert _floats(cliente.get(INVENTORY_URL, {"ordering": "float_value"})) == [
        "0.100000000",
        "0.200000000",
        "0.300000000",
    ]
    assert _floats(cliente.get(INVENTORY_URL, {"ordering": "-float_value"})) == [
        "0.300000000",
        "0.200000000",
        "0.100000000",
    ]


def test_ordena_por_preco_de_referencia(ana: Any) -> None:
    for sufixo, preco in [("a", 300), ("b", 100), ("c", 200)]:
        criar_instancia(ana, criar_skin(f"s-{sufixo}", nome=f"Skin {sufixo}", preco=preco))
    cliente = logado(ana)

    assert _nomes(cliente.get(INVENTORY_URL, {"ordering": "price"})) == [
        "Skin b",
        "Skin c",
        "Skin a",
    ]
    assert _nomes(cliente.get(INVENTORY_URL, {"ordering": "-price"})) == [
        "Skin a",
        "Skin c",
        "Skin b",
    ]


def test_ordena_por_nome(ana: Any) -> None:
    for sufixo in ["c", "a", "b"]:
        criar_instancia(ana, criar_skin(f"s-{sufixo}", nome=f"Skin {sufixo}"))
    cliente = logado(ana)

    assert _nomes(cliente.get(INVENTORY_URL, {"ordering": "name"})) == [
        "Skin a",
        "Skin b",
        "Skin c",
    ]
    assert _nomes(cliente.get(INVENTORY_URL, {"ordering": "-name"})) == [
        "Skin c",
        "Skin b",
        "Skin a",
    ]


def test_ordena_por_data_de_aquisicao(ana: Any, skin: Any) -> None:
    from apps.inventory.models import SkinInstance

    antigo = criar_instancia(ana, skin)
    novo = criar_instancia(ana, skin)
    SkinInstance.objects.filter(pk=antigo.pk).update(acquired_at=datetime(2026, 1, 1, tzinfo=UTC))
    SkinInstance.objects.filter(pk=novo.pk).update(acquired_at=datetime(2026, 6, 1, tzinfo=UTC))
    cliente = logado(ana)

    assert _ids(cliente.get(INVENTORY_URL, {"ordering": "acquired_at"})) == [
        str(antigo.id),
        str(novo.id),
    ]
    assert _ids(cliente.get(INVENTORY_URL, {"ordering": "-acquired_at"})) == [
        str(novo.id),
        str(antigo.id),
    ]


@pytest.mark.parametrize("ordenacao", ["float_value", "price", "name", "-acquired_at"])
def test_itens_com_a_mesma_chave_nao_repetem_nem_somem_entre_paginas(
    ana: Any, skin: Any, ordenacao: str
) -> None:
    criados = {str(criar_instancia(ana, skin, "0.5").id) for _ in range(7)}
    cliente = logado(ana)

    vistos: list[str] = []
    for pagina in (1, 2, 3):
        params = {"ordering": ordenacao, "page_size": 3, "page": pagina}
        vistos += _ids(cliente.get(INVENTORY_URL, params))

    assert len(vistos) == 7
    assert set(vistos) == criados


# --- parâmetros inválidos ------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"ordering": "owner"},
        {"ordering": "-id"},
        {"ordering": "float_value;drop"},
        {"wear": "Factory new"},
        {"wear": "inventado"},
        {"page_size": "0"},
        {"page_size": "-1"},
        {"page_size": "101"},
        {"page_size": "abc"},
        {"q": "x" * 51},
    ],
)
def test_parametro_invalido_do_proprio_dono_da_400(ana: Any, params: dict[str, str]) -> None:
    assert logado(ana).get(INVENTORY_URL, params).status_code == 400


def test_page_size_no_limite_e_aceito(ana: Any, skin: Any) -> None:
    criar_instancia(ana, skin)

    assert logado(ana).get(INVENTORY_URL, {"page_size": "100"}).status_code == 200


# --- custo ---------------------------------------------------------------------------------


def _consultas(cliente: Any) -> int:
    with CaptureQueriesContext(connection) as contexto:
        assert cliente.get(INVENTORY_URL).status_code == 200
    return len(contexto)


def test_o_numero_de_queries_nao_cresce_com_o_numero_de_itens(ana: Any) -> None:
    cliente = logado(ana)
    criar_instancia(ana, criar_skin("s-0"))
    com_um = _consultas(cliente)

    for i in range(1, 25):
        criar_instancia(ana, criar_skin(f"s-{i}"))

    assert _consultas(cliente) == com_um
