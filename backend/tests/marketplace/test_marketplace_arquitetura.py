"""Testes de arquitetura do mercado: regras puras, estados do modelo e posse pelo inventory."""

import ast
import re
from pathlib import Path

import pytest

APPS = Path(__file__).resolve().parents[2] / "apps"
APP = APPS / "marketplace"


def _codigo() -> dict[str, str]:
    return {
        str(a.relative_to(APP)): a.read_text(encoding="utf-8")
        for a in APP.rglob("*.py")
        if "migrations" not in a.parts
    }


def _imports(fonte: str) -> list[str]:
    return [
        linha.strip()
        for linha in fonte.splitlines()
        if linha.lstrip().startswith(("import ", "from "))
    ]


def test_o_app_do_mercado_existe_com_as_camadas_esperadas() -> None:
    codigo = _codigo()

    assert {"models.py", "services.py", "selectors.py", "views.py"} <= set(codigo)


def test_rules_nao_importa_django_nem_outros_apps() -> None:
    """GUIDELINES 5: a regra pura roda sem banco e sem framework."""
    fonte = _codigo()["rules.py"]

    achados = [linha for linha in _imports(fonte) if "django" in linha or "apps." in linha]

    assert achados == []


def test_os_estados_de_rules_sao_os_mesmos_do_modelo() -> None:
    """`rules` é puro e repete os textos dos estados; este teste impede que se separem."""
    from apps.marketplace import rules
    from apps.marketplace.models import ListingStatus

    de_rules = (rules.ACTIVE, rules.SOLD, rules.CANCELLED)

    assert de_rules == tuple(ListingStatus)
    assert set(de_rules) == set(ListingStatus.values)


_PACOTE = ["apps", "marketplace"]  # onde moram os arquivos verificados, para `from . import`
_PROIBIDOS = ("apps.trades", "apps.economy", "apps.friends", "apps.rooms")


def _modulos_importados(fonte: str) -> list[str]:
    """Todo módulo que a árvore (`ast`) importa, em qualquer lugar do arquivo.

    Lê a árvore, não o texto: pega vários imports na mesma linha (`;`), import dentro de função,
    importação relativa (`from .. import trades`), `from apps import trades` e
    `importlib.import_module("...")` com texto literal, e ignora comentário e docstring.
    """
    achados: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Import):
            achados += [alias.name for alias in no.names]
        elif isinstance(no, ast.ImportFrom):
            base = _PACOTE[: len(_PACOTE) - (no.level - 1)] if no.level else []
            modulo = ".".join([*base, *([no.module] if no.module else [])])
            achados.append(modulo)
            if modulo == "apps":
                achados += [f"apps.{alias.name}" for alias in no.names]
        elif isinstance(no, ast.Call) and no.args:
            primeiro = no.args[0]
            nome = getattr(no.func, "id", getattr(no.func, "attr", ""))
            if (
                nome in ("import_module", "__import__")
                and isinstance(primeiro, ast.Constant)
                and isinstance(primeiro.value, str)
            ):
                achados.append(primeiro.value)
    return achados


def test_o_mercado_nao_importa_trades_economy_friends_nem_rooms() -> None:
    """Módulo não importa módulo: a única ponte com `trades` é a guarda registrada em `inventory`.

    O mercado só conhece `accounts`, `catalog` e `inventory`. Quem precisar de carteira (a 4.4)
    ou de amizade decide isso por uma exceção estreita e escrita, como a da view de `trades`.
    """
    for nome, fonte in _codigo().items():
        achados = [
            m
            for m in _modulos_importados(fonte)
            if any(m == p or m.startswith(f"{p}.") for p in _PROIBIDOS)
        ]
        assert achados == [], nome


@pytest.mark.parametrize(
    "fonte",
    [
        "from apps.trades import services",
        "import apps.trades.services",
        "from apps import trades",
        "from .. import trades",
        "from ..economy.services import transfer",
        "import apps.friends; import os",
        "def f():\n    from apps.rooms import models",
        "import importlib\nimportlib.import_module('apps.trades.services')",
    ],
)
def test_o_detector_de_importacao_enxerga_as_formas_de_burlar_o_teste_de_texto(
    fonte: str,
) -> None:
    """O detector tem de achar o que `"apps.trades" in linha` deixava passar."""
    achados = [
        m
        for m in _modulos_importados(fonte)
        if any(m == p or m.startswith(f"{p}.") for p in _PROIBIDOS)
    ]

    assert achados != []


def test_nenhum_arquivo_do_mercado_escreve_o_dono_do_item() -> None:
    """GUIDELINES 2: só `inventory.services` muda o dono. O mercado só lê e recusa."""
    escrita_direta = re.compile(r"\.owner\s*=[^=]|\.owner_id\s*=[^=]|\.update\([^)]*owner")
    achados = [nome for nome, fonte in _codigo().items() if escrita_direta.search(fonte)]

    assert achados == []
