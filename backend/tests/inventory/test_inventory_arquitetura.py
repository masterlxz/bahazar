"""Testes de arquitetura do inventário: fronteiras, porta única de escrita e dinheiro/float."""

import re
from pathlib import Path

APPS = Path(__file__).resolve().parents[2] / "apps"
APP = APPS / "inventory"


def _codigo() -> dict[str, str]:
    return {a.name: a.read_text(encoding="utf-8") for a in APP.rglob("*.py")}


def test_inventory_nao_importa_rooms_nem_economy() -> None:
    """Núcleo não importa núcleo sem motivo: o inventário não conhece grupo nem carteira."""
    proibidos = ("apps.rooms", "apps.economy")
    assert "models.py" in _codigo(), "apps.inventory não existe"
    achados = [
        f"{nome}: {linha.strip()}"
        for nome, fonte in _codigo().items()
        for linha in fonte.splitlines()
        if linha.lstrip().startswith(("import ", "from ")) and any(p in linha for p in proibidos)
    ]

    assert achados == []


def test_so_inventory_services_escreve_instancias() -> None:
    """GUIDELINES 2: nenhuma view, comando ou admin cria instância direto pelo ORM."""
    escritas = "create|bulk_create|get_or_create|update_or_create"
    padrao = re.compile(rf"SkinInstance\.objects\.({escritas})")
    achados = [
        str(arquivo.relative_to(APPS))
        for arquivo in APPS.rglob("*.py")
        if "migrations" not in arquivo.parts
        and arquivo.relative_to(APPS) != Path("inventory/services.py")
        and padrao.search(arquivo.read_text(encoding="utf-8"))
    ]

    assert "services.py" in _codigo(), "apps.inventory.services não existe"
    assert achados == []


def test_float_do_jogo_nao_usa_float_do_python() -> None:
    """O float da skin é `Decimal` de ponta a ponta (nunca `float(`), por exatidão."""
    codigo = _codigo()

    for arquivo in ("rules.py", "services.py"):
        assert "float(" not in codigo[arquivo]
