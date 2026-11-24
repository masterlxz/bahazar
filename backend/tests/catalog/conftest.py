"""Helpers dos testes do catálogo (PR 3.1).

Todos os dados são INVENTADOS: o catálogo e os preços reais pertencem à Valve e à Skinport, e o
repositório é público. Os arquivos imitam só o formato (campos que o import lê).
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ALL_WEARS = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]

Escrever = Callable[..., tuple[Path, Path]]


def skin(
    ext_id: str = "skin-aaa",
    name: str = "AK-47 | Teste",
    *,
    weapon: str = "AK-47",
    rarity: str = "Classified",
    min_float: float = 0.0,
    max_float: float = 1.0,
    collections: list[str] | None = None,
    wears: list[str] | None = None,
) -> dict[str, Any]:
    """Uma entrada do catálogo, só com os campos que o import lê."""
    colecoes = ["Coleção Teste"] if collections is None else collections
    return {
        "id": ext_id,
        "name": name,
        "weapon": {"name": weapon},
        "rarity": {"name": rarity},
        "min_float": min_float,
        "max_float": max_float,
        "collections": [{"name": c} for c in colecoes],
        "wears": [{"name": w} for w in (ALL_WEARS if wears is None else wears)],
    }


def preco(nome: str, desgaste: str, sugerido: float | None) -> dict[str, Any]:
    """Uma linha do snapshot de preços no formato da Skinport."""
    return {
        "market_hash_name": f"{nome} ({desgaste})",
        "suggested_price": sugerido,
        "min_price": None,
        "quantity": 0,
    }


@pytest.fixture
def escrever(tmp_path: Path) -> Escrever:
    """Grava `catalogo.json` e `precos.json` e devolve os dois caminhos."""

    def _escrever(
        catalogo: list[dict[str, Any]], precos: list[dict[str, Any]]
    ) -> tuple[Path, Path]:
        c = tmp_path / "catalogo.json"
        p = tmp_path / "precos.json"
        c.write_text(json.dumps(catalogo), encoding="utf-8")
        p.write_text(json.dumps(precos), encoding="utf-8")
        return c, p

    return _escrever
