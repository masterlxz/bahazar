"""Cadastro: o que é aceito, o que é recusado e a defesa contra CSRF."""

import uuid

import pytest
from rest_framework.test import APIClient

from .conftest import SENHA_FORTE, SIGNUP_URL, User, criar_usuario, csrf_headers

pytestmark = pytest.mark.django_db


def _cadastrar(client: APIClient, **campos: str) -> int:
    corpo = {
        "username": "ana_01",
        "email": "ana@exemplo.com",
        "password": SENHA_FORTE,
        **campos,
    }
    resposta = client.post(SIGNUP_URL, corpo, format="json", **csrf_headers(client))
    return resposta.status_code


def test_cadastro_valido_cria_usuario_com_uuid() -> None:
    client = APIClient(enforce_csrf_checks=True)

    status = _cadastrar(client)

    assert status == 200
    usuario = User.objects.get(username="ana_01")
    assert isinstance(usuario.pk, uuid.UUID)
    assert usuario.email == "ana@exemplo.com"
    assert usuario.check_password(SENHA_FORTE)


def test_cadastro_sem_csrf_e_recusado() -> None:
    client = APIClient(enforce_csrf_checks=True)

    resposta = client.post(
        SIGNUP_URL,
        {"username": "ana_01", "email": "ana@exemplo.com", "password": SENHA_FORTE},
        format="json",
    )

    assert resposta.status_code == 403
    assert not User.objects.filter(username="ana_01").exists()


def test_nome_de_usuario_e_unico_sem_distinguir_maiusculas() -> None:
    criar_usuario(username="ana_01", email="ana@exemplo.com")
    client = APIClient(enforce_csrf_checks=True)

    status = _cadastrar(client, username="Ana_01", email="outra@exemplo.com")

    assert status == 400
    assert User.objects.filter(username__iexact="ana_01").count() == 1


@pytest.mark.parametrize(
    "username",
    ["ab", "a-b!", "x" * 21, "com espaco", "admin", "system", "root", "bahazar"],
)
def test_nome_de_usuario_invalido_ou_reservado_e_recusado(username: str) -> None:
    client = APIClient(enforce_csrf_checks=True)

    status = _cadastrar(client, username=username)

    assert status == 400
    assert User.objects.count() == 0


@pytest.mark.parametrize("senha", ["12345678", "password123", "Abc1234!x"])
def test_senha_fraca_e_recusada(senha: str) -> None:
    # 12345678 = só números; password123 = na lista de senhas comuns do Django (que é em inglês:
    # senhas fracas em português NÃO são barradas); Abc1234!x = 9 caracteres (mínimo é 10).
    client = APIClient(enforce_csrf_checks=True)

    status = _cadastrar(client, password=senha)

    assert status == 400
    assert User.objects.count() == 0


def test_email_duplicado_e_recusado_sem_distinguir_maiusculas() -> None:
    criar_usuario(username="ana_01", email="ana@exemplo.com")
    client = APIClient(enforce_csrf_checks=True)

    _cadastrar(client, username="bia_02", email="ANA@exemplo.com")

    assert not User.objects.filter(username="bia_02").exists()
