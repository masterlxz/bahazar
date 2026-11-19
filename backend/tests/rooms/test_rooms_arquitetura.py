"""Teste de arquitetura: nenhuma view de salas pode depender só do padrão por omissão.

O padrão do projeto já é negar (`IsAuthenticated`), mas em dados de sala isso NÃO basta: precisa
declarar quem é membro ou admin. Uma view nova sem permissão explícita falha aqui, no CI.
"""

import importlib
import inspect

from rest_framework.views import APIView


def test_toda_view_de_salas_declara_permissao_explicita() -> None:
    views = importlib.import_module("apps.rooms.views")

    classes = [
        c
        for _, c in inspect.getmembers(views, inspect.isclass)
        if issubclass(c, APIView) and c.__module__ == views.__name__
    ]

    assert classes, "apps.rooms.views não define nenhuma view"
    sem_permissao = [c.__name__ for c in classes if not c.__dict__.get("permission_classes")]
    assert sem_permissao == [], f"views de salas sem permission_classes próprio: {sem_permissao}"
