"""Login, sessão, logout e limite de tentativas."""

import pytest
from rest_framework.test import APIClient

from .conftest import LOGIN_URL, ME_URL, SENHA_FORTE, SESSION_URL, criar_usuario, csrf_headers

pytestmark = pytest.mark.django_db


def _login(client: APIClient, **credenciais: str) -> int:
    resposta = client.post(LOGIN_URL, credenciais, format="json", **csrf_headers(client))
    return resposta.status_code


def test_login_com_nome_de_usuario_cria_sessao() -> None:
    criar_usuario()
    client = APIClient(enforce_csrf_checks=True)

    assert _login(client, username="ana_01", password=SENHA_FORTE) == 200
    assert client.get(SESSION_URL).status_code == 200


def test_login_com_email_cria_sessao() -> None:
    criar_usuario()
    client = APIClient(enforce_csrf_checks=True)

    assert _login(client, email="ana@exemplo.com", password=SENHA_FORTE) == 200
    assert client.get(SESSION_URL).status_code == 200


def test_senha_errada_nao_cria_sessao() -> None:
    criar_usuario()
    client = APIClient(enforce_csrf_checks=True)

    assert _login(client, username="ana_01", password="senha-errada-123") == 400
    assert client.get(SESSION_URL).status_code == 401


def test_tentativas_demais_bloqueiam_ate_a_senha_certa_entrar() -> None:
    criar_usuario()
    client = APIClient(enforce_csrf_checks=True)

    for _ in range(12):
        _login(client, username="ana_01", password="senha-errada-123")

    # Bloqueado: nem a senha CERTA entra mais (o allauth responde 400 com erro de limite).
    assert _login(client, username="ana_01", password=SENHA_FORTE) in (400, 429)
    assert client.get(SESSION_URL).status_code == 401


def test_logout_invalida_a_sessao() -> None:
    criar_usuario()
    client = APIClient(enforce_csrf_checks=True)
    _login(client, username="ana_01", password=SENHA_FORTE)

    client.delete(SESSION_URL, **csrf_headers(client))

    assert client.get(SESSION_URL).status_code == 401
    assert client.get(ME_URL).status_code in (401, 403)
