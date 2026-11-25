"""Testes de arquitetura das trocas: fronteiras e a porta única de posse (GUIDELINES 2, 5 e 7)."""

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
_ECONOMY_PERMITIDO = re.compile(
    r"^(from apps\.economy\.(idempotency|rules) import |import apps\.economy\.(idempotency|rules)$)"
)
_ROOMS_OU_ECONOMY = re.compile(r"\b(rooms|economy)\b")


def _importacoes_proibidas(codigo: dict[str, str]) -> list[str]:
    """`rooms` em qualquer arquivo e `economy` fora da exceção estreita da view."""
    achados = []
    for nome, fonte in codigo.items():
        for linha in _imports(fonte):
            if not _ROOMS_OU_ECONOMY.search(linha):
                continue
            so_economy = "rooms" not in linha
            if nome == _VIEW_DA_EXCECAO and so_economy and _ECONOMY_PERMITIDO.match(linha):
                continue
            achados.append(f"{nome}: {linha}")
    return achados


def test_trades_nao_importa_rooms_e_so_a_view_importa_idempotencia_e_regras_do_economy() -> None:
    codigo = _codigo()
    assert "models.py" in codigo, "apps.trades não existe"
    assert _VIEW_DA_EXCECAO in codigo, "apps.trades.views não existe"

    assert _importacoes_proibidas(codigo) == []

    # a exceção existe de fato: a view importa os dois módulos, e só eles
    do_economy = [linha for linha in _imports(codigo[_VIEW_DA_EXCECAO]) if "economy" in linha]
    assert any("apps.economy.idempotency" in linha for linha in do_economy)
    assert any("apps.economy.rules" in linha for linha in do_economy)


def _caso(nome: str, arquivo: str, linha: str) -> Any:
    return pytest.param(arquivo, linha, id=nome)


@pytest.mark.parametrize(
    ("arquivo", "linha"),
    [
        _caso("outro-arquivo-rules", "services.py", "from apps.economy.rules import x"),
        _caso("outro-arquivo-idem", "selectors.py", "from apps.economy.idempotency import x"),
        _caso("outro-arquivo-import", "serializers.py", "import apps.economy.rules"),
        _caso("view-ledger", "views.py", "from apps.economy.services import transfer"),
        _caso("view-carteira", "views.py", "from apps.economy.models import Wallet"),
        _caso("view-pacote", "views.py", "from apps.economy import services"),
        _caso("view-pacote-sem-ponto", "views.py", "from apps import economy"),
        _caso("view-rooms", "views.py", "from apps.rooms.services import create_room"),
        _caso("rooms-dentro-de-funcao", "models.py", "    from apps.rooms import models"),
    ],
)
def test_o_teste_de_fronteira_cai_com_importacao_fora_da_excecao(arquivo: str, linha: str) -> None:
    assert _importacoes_proibidas({arquivo: linha}) == [f"{arquivo}: {linha.strip()}"]


@pytest.mark.parametrize(
    "linha",
    [
        "from apps.economy.idempotency import IdempotencyKeyReused, run_once",
        "from apps.economy.rules import normalize_idempotency_key, request_fingerprint",
        "import apps.economy.idempotency",
    ],
)
def test_o_teste_de_fronteira_aceita_so_a_excecao_da_view(linha: str) -> None:
    assert _importacoes_proibidas({"views.py": linha}) == []


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
