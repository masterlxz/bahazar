"""Testes de arquitetura do inventário: fronteiras, porta única de escrita e dinheiro/float."""

import importlib
import inspect
import re
from pathlib import Path

from rest_framework.views import APIView

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
    chamada = re.compile(r"\bfloat\(")  # `draw_float(` não conta: o `_` é parte da palavra

    for arquivo in ("rules.py", "services.py"):
        assert chamada.search(codigo[arquivo]) is None


# --- API (PR 3.2b) -------------------------------------------------------------------------


def test_toda_view_do_inventario_declara_permissao_explicita() -> None:
    views = importlib.import_module("apps.inventory.views")

    classes = [
        c
        for _, c in inspect.getmembers(views, inspect.isclass)
        if issubclass(c, APIView) and c.__module__ == views.__name__
    ]

    assert classes, "apps.inventory.views não define nenhuma view"
    sem = [c.__name__ for c in classes if not c.__dict__.get("permission_classes")]
    assert sem == [], f"views do inventário sem permission_classes próprio: {sem}"


def test_a_visibilidade_so_e_decidida_por_can_view() -> None:
    """R1: a view consulta `friends.selectors` e nunca compara status de amizade."""
    fonte = _codigo()["views.py"]

    assert "can_view" in fonte
    assert "find_user" in fonte
    assert '"accepted"' not in fonte
    assert "apps.friends.models" not in fonte
    assert "Friendship" not in fonte


def test_a_view_nao_le_o_banco_direto() -> None:
    """GUIDELINES 6: leitura de dado de jogo só por selector escopado ao dono."""
    fonte = _codigo()["views.py"]

    assert ".objects" not in fonte
    assert "SkinInstance" not in fonte
    assert "inventory_of" in fonte


def test_o_serializer_tem_campos_explicitos_e_nao_expoe_dado_interno() -> None:
    fonte = _codigo()["serializers.py"]

    assert "__all__" not in fonte
    for proibido in ("acquired_via", "acquired_ref_id", "consumed_at", "owner"):
        assert proibido not in fonte, f"o serializer não pode expor {proibido}"
