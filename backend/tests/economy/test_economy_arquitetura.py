"""Testes de arquitetura da economia: direção das dependências e permissão explícita."""

import importlib
import inspect
import re
from pathlib import Path

from rest_framework.views import APIView

APPS = Path(__file__).resolve().parents[2] / "apps"


def test_toda_view_da_economia_declara_permissao_explicita() -> None:
    views = importlib.import_module("apps.economy.views")

    classes = [
        c
        for _, c in inspect.getmembers(views, inspect.isclass)
        if issubclass(c, APIView) and c.__module__ == views.__name__
    ]

    assert classes, "apps.economy.views não define nenhuma view"
    sem = [c.__name__ for c in classes if not c.__dict__.get("permission_classes")]
    assert sem == [], f"views da economia sem permission_classes próprio: {sem}"


def test_accounts_nao_importa_economy() -> None:
    """A economia escuta o `accounts` (sinal de criação de usuário), nunca o contrário."""
    importa_economy = re.compile(r"^\s*(from|import)\s+(apps\.economy|\.+economy)\b", re.MULTILINE)

    infratores = [
        str(arquivo.relative_to(APPS))
        for arquivo in (APPS / "accounts").rglob("*.py")
        if importa_economy.search(arquivo.read_text(encoding="utf-8"))
    ]

    assert infratores == []
