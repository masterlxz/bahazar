"""Os system checks do Django.

O pytest cria o banco de teste por dentro e NÃO roda os system checks; o `migrate` e o
`runserver` rodam. Um nome de índice com mais de 30 caracteres (`models.E034`) passou por mais de
quinhentos testes verdes e só apareceu no primeiro `migrate` de verdade. Este teste fecha essa
lacuna: falha se `manage.py check` acusar erro ou aviso.

O `migrate` chama `check(databases=[banco])`; o teste faz o mesmo, para pegar também as
checagens que dependem do banco.

(Modelo alterado sem migração já é coberto por `accounts/test_constraints.py`:
`test_nao_ha_migracao_pendente`.)
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import SystemCheckError


@pytest.mark.django_db
def test_system_checks_do_django_passam() -> None:
    saida, erros = StringIO(), StringIO()

    try:
        call_command("check", databases=["default"], stdout=saida, stderr=erros)
    except SystemCheckError as erro:  # a mensagem lista cada erro (ex.: models.E034)
        pytest.fail(f"manage.py check falhou:\n{erro}")

    assert "no issues" in saida.getvalue(), f"manage.py check acusou avisos:\n{erros.getvalue()}"
