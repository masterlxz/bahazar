"""Testes de arquitetura de `friends`: a regra de visibilidade tem um lugar só (R1)."""

import importlib
import inspect
from pathlib import Path

from rest_framework.views import APIView

APP = Path(__file__).resolve().parents[2] / "apps" / "friends"


def test_toda_view_de_amizades_declara_permissao_explicita() -> None:
    views = importlib.import_module("apps.friends.views")

    classes = [
        c
        for _, c in inspect.getmembers(views, inspect.isclass)
        if issubclass(c, APIView) and c.__module__ == views.__name__
    ]

    assert classes, "apps.friends.views não define nenhuma view"
    sem_permissao = [c.__name__ for c in classes if not c.__dict__.get("permission_classes")]
    assert sem_permissao == [], f"views de amizades sem permission_classes próprio: {sem_permissao}"


def test_friends_nao_importa_outros_apps_de_jogo() -> None:
    """Núcleo não importa núcleo: friends só conhece `accounts` (o usuário)."""
    proibidos = ("apps.rooms", "apps.economy")
    achados = [
        f"{arquivo.name}: {linha.strip()}"
        for arquivo in APP.glob("*.py")
        for linha in arquivo.read_text().splitlines()
        if linha.lstrip().startswith(("import ", "from ")) and any(p in linha for p in proibidos)
    ]

    assert achados == []


def test_friends_nao_importa_trades_nem_inventory() -> None:
    """`trades` importa `friends` (para `can_view`): o caminho inverso fecharia um ciclo.

    Quem precisa reagir ao fim de um par registra um gancho em `friends.hooks`; é assim que
    `trades` cancela as ofertas pendentes sem que `friends` o conheça.
    """
    achados = [
        f"{arquivo.name}: {linha.strip()}"
        for arquivo in APP.glob("*.py")
        for linha in arquivo.read_text().splitlines()
        if linha.lstrip().startswith(("import ", "from "))
        and any(p in linha for p in ("apps.trades", "apps.inventory"))
    ]

    assert achados == []


def test_a_regra_de_visibilidade_so_e_decidida_em_rules() -> None:
    """Nenhuma view compara status de amizade: elas chamam `selectors.can_view`."""
    fonte = (APP / "views.py").read_text()

    assert "can_view" in fonte
    assert '"accepted"' not in fonte
