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


def _importacoes(fonte: str) -> list[tuple[str, str | None]]:
    """Todo `(módulo, nome)` que a árvore (`ast`) importa, em qualquer lugar do arquivo.

    Lê a árvore, não o texto: pega vários imports na mesma linha (`;`), import dentro de função,
    importação relativa (`from .. import trades`), `from apps import trades` e
    `importlib.import_module("...")` com texto literal, e ignora comentário e docstring.

    `nome` é o que `from <módulo> import <nome>` traz (o nome ORIGINAL, não o apelido; `*` fica
    `"*"`). É `None` quando o import entrega o módulo inteiro (`import a.b`, `import_module`,
    `from apps import trades`): quem o recebe alcança qualquer atributo dele.
    """
    achados: list[tuple[str, str | None]] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Import):
            achados += [(alias.name, None) for alias in no.names]
        elif isinstance(no, ast.ImportFrom):
            base = _PACOTE[: len(_PACOTE) - (no.level - 1)] if no.level else []
            modulo = ".".join([*base, *([no.module] if no.module else [])])
            if modulo == "apps":
                achados += [(f"apps.{alias.name}", None) for alias in no.names]
            else:
                achados += [(modulo, alias.name) for alias in no.names]
        elif isinstance(no, ast.Call) and no.args:
            primeiro = no.args[0]
            nome = getattr(no.func, "id", getattr(no.func, "attr", ""))
            if (
                nome in ("import_module", "__import__")
                and isinstance(primeiro, ast.Constant)
                and isinstance(primeiro.value, str)
            ):
                achados.append((primeiro.value, None))
    return achados


def _modulos_importados(fonte: str) -> list[str]:
    """Só os módulos de `_importacoes`, sem os nomes."""
    return [modulo for modulo, _ in _importacoes(fonte)]


# As exceções estreitas e escritas: só a view lê o bloqueio, pelo selector do `friends` (ADR 0017);
# só o serviço de compra fala com o dinheiro, por `economy.services`, e roda o `run_once` por
# dentro (ADR 0018). Nenhum outro arquivo do mercado, nenhum outro módulo de `economy`.
#
# A exceção é por MÓDULO E POR NOME (`from <módulo> import <nome>`): `economy.services` importa
# `Wallet` do modelo e o expõe como atributo, então liberar o módulo inteiro liberaria a carteira.
# `import <módulo>` solto também não vale: dá acesso a qualquer atributo, e o `ast` só vê o módulo.
_ECONOMY_DO_SERVICO = {
    "apps.economy.services": frozenset(
        {"Entry", "InsufficientFunds", "ensure_wallet", "get_system_wallet", "post_entries"}
    ),
    "apps.economy.idempotency": frozenset({"IdempotencyKeyReused", "run_once"}),
    "apps.economy.rules": frozenset({"normalize_idempotency_key", "request_fingerprint"}),
}
_FRIENDS_DA_VIEW = {"apps.friends.selectors": frozenset({"blocked_by"})}
_EXCECOES: dict[str, dict[str, frozenset[str]]] = {
    "views.py": _FRIENDS_DA_VIEW,
    "services.py": _ECONOMY_DO_SERVICO,
}


def _proibidos_importados(nome: str, fonte: str) -> list[str]:
    """Os imports proibidos de `fonte`, como `módulo.nome` (ou só `módulo` se vier inteiro)."""
    permitidos = _EXCECOES.get(nome, {})
    return [
        f"{modulo}.{importado}" if importado else modulo
        for modulo, importado in _importacoes(fonte)
        if any(modulo == p or modulo.startswith(f"{p}.") for p in _PROIBIDOS)
        and importado != "*"
        and (importado is None or importado not in permitidos.get(modulo, frozenset()))
    ]


def _nomes_sobrando(nome: str, fonte: str) -> list[str]:
    """Nomes da exceção de `nome` que `fonte` já não importa: a lista envelheceu e deve encolher.

    Exceção que sobra é porta aberta sem uso: o próximo import desse nome passaria sem ninguém
    ter decidido isso.
    """
    return [
        f"{modulo}.{n}"
        for modulo, permitidos in _EXCECOES.get(nome, {}).items()
        for n in sorted(permitidos - {i for m, i in _importacoes(fonte) if m == modulo and i})
    ]


def test_o_mercado_nao_importa_trades_economy_friends_nem_rooms() -> None:
    """Módulo não importa módulo: a única ponte com `trades` é a guarda registrada em `inventory`.

    O mercado só conhece `accounts`, `catalog` e `inventory`. As exceções são `_EXCECOES`: a view
    lê o bloqueio por `friends.selectors` (ADR 0017) e o serviço de compra fala com o dinheiro
    por `economy` (ADR 0018).
    """
    for nome, fonte in _codigo().items():
        assert _proibidos_importados(nome, fonte) == [], nome


def test_a_view_do_mercado_usa_a_excecao_do_friends_e_so_ela() -> None:
    """A exceção não pode ficar velha: `views.py` importa o selector, e nenhum outro `friends`."""
    codigo = _codigo()

    achados = [m for m in _modulos_importados(codigo["views.py"]) if m.startswith("apps.friends")]

    assert achados == ["apps.friends.selectors"]
    assert _nomes_sobrando("views.py", codigo["views.py"]) == []  # sem nome sobrando na lista
    for nome in ("selectors.py", "services.py", "serializers.py", "models.py"):
        assert [m for m in _modulos_importados(codigo[nome]) if "friends" in m] == [], nome


def test_o_servico_do_mercado_usa_a_excecao_do_economy_e_so_ela() -> None:
    """A ponte com o dinheiro: `services.py` importa `economy.services` e `economy.idempotency`,
    nunca o modelo da carteira; nenhum outro arquivo do mercado importa `economy`."""
    codigo = _codigo()

    achados = {m for m in _modulos_importados(codigo["services.py"]) if "economy" in m}

    assert {"apps.economy.services", "apps.economy.idempotency"} <= achados
    assert achados <= set(_ECONOMY_DO_SERVICO)
    assert _nomes_sobrando("services.py", codigo["services.py"]) == []  # sem nome sobrando
    for nome in ("views.py", "selectors.py", "serializers.py", "models.py", "guards.py"):
        assert [m for m in _modulos_importados(codigo[nome]) if "economy" in m] == [], nome


@pytest.mark.parametrize(
    "fonte",
    [
        "from apps.friends import models",
        "from apps.friends.models import Friendship",
        "from apps.friends import services",
        "import apps.friends.services",
        "from apps.friends.selectors import find_user",  # o módulo é o da exceção; o nome, não
        "from apps.friends.selectors import blocked_by, find_user",
        "from apps.friends.selectors import *",
        "import apps.friends.selectors",
    ],
)
def test_a_excecao_da_view_nao_abre_outros_modulos_do_friends(fonte: str) -> None:
    assert _proibidos_importados("views.py", fonte) != []
    assert _proibidos_importados("views.py", "from apps.friends.selectors import blocked_by") == []
    assert _proibidos_importados("selectors.py", "from apps.friends.selectors import blocked_by")


@pytest.mark.parametrize(
    "fonte",
    [
        "from apps.economy import models",
        "from apps.economy.models import Wallet",
        "from apps.economy import services",
        "import apps.economy.audit",
        "from apps.friends.selectors import blocked_by",
        # o módulo é o da exceção; o nome não (`services` re-exporta o modelo da carteira)
        "from apps.economy.services import Wallet",
        "from apps.economy.services import post_entries, Wallet",
        "from apps.economy.services import Wallet as Carteira",
        "from apps.economy.services import *",
        "from apps.economy.idempotency import IdempotencyRecord",
        "from apps.economy.rules import validate_entries",
        # `import <módulo>` solto alcança qualquer atributo
        "import apps.economy.services",
        "import importlib\nimportlib.import_module('apps.economy.services')",
        "from ..economy.services import Wallet",
    ],
)
def test_a_excecao_do_servico_nao_abre_outros_modulos(fonte: str) -> None:
    assert _proibidos_importados("services.py", fonte) != []


def test_excecao_com_nome_que_o_arquivo_nao_importa_mais_e_apontada_como_velha() -> None:
    """O detector de exceção velha tem de enxergar o nome que sobra (e não inventar um)."""
    fonte = "from apps.friends.selectors import blocked_by"
    so_um = "from apps.economy.services import post_entries"

    assert _nomes_sobrando("views.py", fonte) == []
    assert _nomes_sobrando("views.py", "import os") == ["apps.friends.selectors.blocked_by"]
    assert "apps.economy.services.Entry" in _nomes_sobrando("services.py", so_um)
    assert "apps.economy.services.post_entries" not in _nomes_sobrando("services.py", so_um)


@pytest.mark.parametrize(
    "fonte",
    [
        "from apps.economy.services import post_entries",
        "from apps.economy.idempotency import run_once",
        "from apps.economy.rules import normalize_idempotency_key",
    ],
)
def test_a_excecao_do_servico_vale_so_no_servico(fonte: str) -> None:
    assert _proibidos_importados("services.py", fonte) == []
    for outro in ("views.py", "selectors.py", "serializers.py", "models.py"):
        assert _proibidos_importados(outro, fonte) != [], outro


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
