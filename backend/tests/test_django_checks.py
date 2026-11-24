"""Os checks do Django e a coerência entre modelos e migrações.

O pytest cria o banco de teste por dentro e NÃO roda os system checks; o `migrate` e o
`runserver` rodam. Um nome de índice com mais de 30 caracteres (`models.E034`) passou por 540
testes verdes e só apareceu no primeiro `migrate` de verdade. Estes testes fecham essa lacuna:
falham se `manage.py check` acusar qualquer erro ou se um modelo mudou sem a migração.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import SystemCheckError


def test_system_checks_do_django_passam() -> None:
    saida = StringIO()

    try:
        call_command("check", stdout=saida)
    except SystemCheckError as erro:  # a mensagem lista cada erro (ex.: models.E034)
        pytest.fail(f"manage.py check falhou:\n{erro}")

    assert "no issues" in saida.getvalue()


@pytest.mark.django_db
def test_modelos_e_migracoes_estao_em_dia() -> None:
    saida = StringIO()

    try:
        call_command("makemigrations", check=True, dry_run=True, stdout=saida)
    except SystemExit:  # `--check` sai com status 1 quando faltaria uma migração
        pytest.fail(f"faltam migrações para os modelos:\n{saida.getvalue()}")

    assert "No changes detected" in saida.getvalue()
