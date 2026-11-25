"""Testes de arquitetura das trocas: fronteiras e a porta única de posse (GUIDELINES 2, 5 e 7)."""

import re
from pathlib import Path

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


def test_trades_nao_importa_rooms_nem_economy() -> None:
    """A troca é só de itens, sem dinheiro: não conhece grupo nem carteira."""
    proibidos = ("apps.rooms", "apps.economy")
    assert "models.py" in _codigo(), "apps.trades não existe"
    achados = [
        f"{nome}: {linha}"
        for nome, fonte in _codigo().items()
        for linha in _imports(fonte)
        if any(p in linha for p in proibidos)
    ]

    assert achados == []


def test_rules_nao_importa_django_nem_outros_apps() -> None:
    """GUIDELINES 5: o núcleo puro roda sem banco e sem framework."""
    fonte = _codigo()["rules.py"]

    achados = [linha for linha in _imports(fonte) if "django" in linha or "apps." in linha]

    assert achados == []


def test_ninguem_fora_de_inventory_services_troca_dono_de_item() -> None:
    """GUIDELINES 2: `trades` chama `change_owner`; nunca escreve `owner` da instância."""
    escrita_direta = re.compile(r"\.owner\s*=[^=]|\.owner_id\s*=[^=]|\.update\([^)]*owner")
    achados = [nome for nome, fonte in _codigo().items() if escrita_direta.search(fonte)]

    assert "services.py" in _codigo(), "apps.trades.services não existe"
    assert "change_owner" in _codigo()["services.py"]
    assert achados == []
