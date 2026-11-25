"""Testes de arquitetura das trocas: fronteiras e a porta única de posse (GUIDELINES 2, 5 e 7)."""

import ast
import re
from pathlib import Path
from typing import Any

import pytest

APPS = Path(__file__).resolve().parents[2] / "apps"
APP = APPS / "trades"


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


# A troca é só de itens, sem dinheiro: não conhece grupo nem carteira. Única exceção (decisão do
# dono, 2026-11-25): a view da API usa a idempotência e as regras puras (`normalize_idempotency_key`
# e `request_fingerprint`) do economy. Carteira e ledger (`models`, `services`) seguem proibidos.
_VIEW_DA_EXCECAO = "views.py"
_PERMITIDOS_NA_VIEW = ("apps.economy.idempotency", "apps.economy.rules")
_PACOTE = ["apps", "trades"]  # onde moram os arquivos verificados, para resolver `from . import`


def _dentro_de(modulo: str, pacote: str) -> bool:
    return modulo == pacote or modulo.startswith(f"{pacote}.")


def _modulo_do_from(no: ast.ImportFrom) -> str:
    """O módulo absoluto de `from <módulo> import ...`, também para importação relativa."""
    if no.level == 0:
        return no.module or ""
    base = _PACOTE[: len(_PACOTE) - (no.level - 1)]
    return ".".join([*base, *([no.module] if no.module else [])])


def _alvos_importados(no: ast.AST) -> list[tuple[str, bool]]:
    """Os módulos que um nó da árvore importa, cada um com a marca "importação dinâmica".

    Em `from apps.economy import services` e `from apps import economy`, o nome importado pode
    ser um submódulo: o alvo é `apps.economy.services` e `apps.economy`, respectivamente.
    """
    if isinstance(no, ast.Import):
        return [(alias.name, False) for alias in no.names]
    if isinstance(no, ast.ImportFrom):
        modulo = _modulo_do_from(no)
        if modulo in ("apps", "apps.economy", "apps.rooms"):
            return [(f"{modulo}.{alias.name}", False) for alias in no.names]
        return [(modulo, False)]
    if isinstance(no, ast.Call) and no.args:
        func, primeiro = no.func, no.args[0]
        nome = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if (
            nome in ("import_module", "__import__")
            and isinstance(primeiro, ast.Constant)
            and isinstance(primeiro.value, str)
        ):
            return [(primeiro.value, True)]
    return []


def _importacoes_proibidas(codigo: dict[str, str]) -> list[str]:
    """`rooms` em qualquer arquivo e `economy` fora da exceção estreita da view.

    Lê a árvore (`ast`), não o texto: vale para vários imports na mesma linha (`;`), para
    import dentro de função e para `importlib.import_module("...")` com texto literal, e
    ignora comentário e docstring que só citam a palavra. Uma importação dinâmica nunca é a
    exceção: ela escaparia da leitura estática.
    """
    achados = []
    for nome, fonte in codigo.items():
        for no in ast.walk(ast.parse(fonte)):
            for alvo, dinamico in _alvos_importados(no):
                if _dentro_de(alvo, "apps.rooms"):
                    achados.append(f"{nome}: {alvo}")
                elif _dentro_de(alvo, "apps.economy"):
                    permitido = (
                        nome == _VIEW_DA_EXCECAO
                        and not dinamico
                        and any(_dentro_de(alvo, p) for p in _PERMITIDOS_NA_VIEW)
                    )
                    if not permitido:
                        achados.append(f"{nome}: {alvo}")
    return achados


def test_trades_nao_importa_rooms_e_so_a_view_importa_idempotencia_e_regras_do_economy() -> None:
    codigo = _codigo()
    assert "models.py" in codigo, "apps.trades não existe"
    assert _VIEW_DA_EXCECAO in codigo, "apps.trades.views não existe"

    assert _importacoes_proibidas(codigo) == []

    # a exceção existe de fato: a view importa os dois módulos
    da_view = {
        alvo
        for no in ast.walk(ast.parse(codigo[_VIEW_DA_EXCECAO]))
        for alvo, _ in _alvos_importados(no)
    }
    assert set(_PERMITIDOS_NA_VIEW) <= da_view


_RULES = "apps.economy.rules"
_IDEM = "apps.economy.idempotency"
_SERV = "apps.economy.services"
_MODELS = "apps.economy.models"


def _caso(nome: str, arquivo: str, fonte: str, alvo: str) -> Any:
    return pytest.param(arquivo, fonte, alvo, id=nome)


@pytest.mark.parametrize(
    ("arquivo", "fonte", "alvo"),
    [
        _caso("outro-arquivo-rules", "services.py", f"from {_RULES} import x", _RULES),
        _caso("outro-arquivo-idem", "selectors.py", f"from {_IDEM} import x", _IDEM),
        _caso("outro-arquivo-import", "serializers.py", f"import {_RULES}", _RULES),
        _caso("view-ledger", "views.py", f"from {_SERV} import t", _SERV),
        _caso("view-carteira", "views.py", "from apps.economy.models import W", _MODELS),
        _caso("view-pacote", "views.py", "from apps.economy import services", _SERV),
        _caso("view-pacote-sem-ponto", "views.py", "from apps import economy", "apps.economy"),
        _caso("view-relativo", "views.py", "from .. import economy", "apps.economy"),
        _caso("view-rooms", "views.py", "from apps.rooms.services import c", "apps.rooms.services"),
        _caso("rooms-func", "models.py", "def f():\n from apps.rooms import x", "apps.rooms.x"),
        _caso(
            "view-ponto-e-virgula",
            "views.py",
            f"from {_RULES} import x; from {_SERV} import y",
            _SERV,
        ),
        _caso(
            "view-import-module",
            "views.py",
            f"import importlib\nimportlib.import_module('{_RULES}')\n",
            _RULES,
        ),
        _caso(
            "view-import-module-direto",
            "views.py",
            f"from importlib import import_module\nimport_module('{_SERV}')\n",
            _SERV,
        ),
        _caso("view-dunder-import", "views.py", f"__import__('{_RULES}')", _RULES),
    ],
)
def test_o_teste_de_fronteira_cai_com_importacao_fora_da_excecao(
    arquivo: str, fonte: str, alvo: str
) -> None:
    assert _importacoes_proibidas({arquivo: fonte}) == [f"{arquivo}: {alvo}"]


@pytest.mark.parametrize(
    "fonte",
    [
        f"from {_IDEM} import IdempotencyKeyReused, run_once",
        f"from {_RULES} import normalize_idempotency_key, request_fingerprint",
        f"import {_IDEM}",
        "from apps.economy import idempotency",
        '"""Fala de economy e rooms."""\n# from apps.economy.services import x\nx = "import y"',
    ],
)
def test_o_teste_de_fronteira_aceita_so_a_excecao_da_view(fonte: str) -> None:
    assert _importacoes_proibidas({"views.py": fonte}) == []


def test_o_teste_de_fronteira_ignora_comentario_e_docstring_em_qualquer_arquivo() -> None:
    fonte = '"""O economy e os rooms ficam fora."""\n# import apps.rooms\nx = "import apps.economy"'

    assert _importacoes_proibidas({"services.py": fonte}) == []


def test_rules_nao_importa_django_nem_outros_apps() -> None:
    """GUIDELINES 5: o núcleo puro roda sem banco e sem framework."""
    fonte = _codigo()["rules.py"]

    achados = [linha for linha in _imports(fonte) if "django" in linha or "apps." in linha]

    assert achados == []


def test_os_estados_de_rules_sao_os_mesmos_do_modelo() -> None:
    """`rules` é puro e repete os textos dos estados; este teste impede que se separem."""
    from apps.trades import rules
    from apps.trades.models import TradeStatus

    de_rules = (rules.PENDING, rules.ACCEPTED, rules.DECLINED, rules.CANCELLED)

    assert de_rules == tuple(TradeStatus)
    assert set(de_rules) == set(TradeStatus.values)


def test_ninguem_fora_de_inventory_services_troca_dono_de_item() -> None:
    """GUIDELINES 2: `trades` chama `change_owner`; nunca escreve `owner` da instância."""
    escrita_direta = re.compile(r"\.owner\s*=[^=]|\.owner_id\s*=[^=]|\.update\([^)]*owner")
    achados = [nome for nome, fonte in _codigo().items() if escrita_direta.search(fonte)]

    assert "services.py" in _codigo(), "apps.trades.services não existe"
    assert "change_owner" in _codigo()["services.py"]
    assert achados == []
