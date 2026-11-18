"""Health check: o serviço responde e diz se o banco está acessível."""

import pytest
from django.db import OperationalError, connection
from rest_framework.test import APIClient

HEALTH_URL = "/api/v1/health/"


@pytest.mark.django_db
def test_health_ok_sem_autenticacao() -> None:
    response = APIClient().get(HEALTH_URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_503_quando_o_banco_cai(monkeypatch: pytest.MonkeyPatch) -> None:
    def banco_fora(*args: object, **kwargs: object) -> None:
        raise OperationalError("conexão recusada")

    monkeypatch.setattr(connection, "cursor", banco_fora)

    response = APIClient().get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error"}
