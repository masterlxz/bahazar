"""Perfil do próprio jogador: o que pode ser lido, o que pode ser alterado e o que é ignorado."""

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

from .conftest import ME_URL, criar_usuario, csrf_headers

pytestmark = pytest.mark.django_db


def _logado() -> tuple[APIClient, Any]:
    usuario = criar_usuario()
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(usuario)
    return client, usuario


def test_anonimo_nao_le_o_perfil() -> None:
    resposta = APIClient().get(ME_URL)

    assert resposta.status_code in (401, 403)


def test_perfil_expoe_so_os_campos_publicos_do_proprio_usuario() -> None:
    client, usuario = _logado()

    resposta = client.get(ME_URL)

    assert resposta.status_code == 200
    assert set(resposta.json()) == {"id", "username", "email", "avatar"}
    assert resposta.json()["id"] == str(usuario.pk)
    assert resposta.json()["avatar"] == "default"


def test_troca_de_avatar_valido() -> None:
    client, usuario = _logado()

    resposta = client.patch(ME_URL, {"avatar": "ember"}, format="json", **csrf_headers(client))

    assert resposta.status_code == 200
    usuario.refresh_from_db()
    assert usuario.avatar == "ember"


@pytest.mark.parametrize("avatar", ["nao-existe", "https://evil.exemplo/x.png", "", "EMBER"])
def test_avatar_fora_da_lista_e_recusado(avatar: str) -> None:
    client, usuario = _logado()

    resposta = client.patch(ME_URL, {"avatar": avatar}, format="json", **csrf_headers(client))

    assert resposta.status_code == 400
    usuario.refresh_from_db()
    assert usuario.avatar == "default"


def test_campos_sensiveis_sao_ignorados_no_patch() -> None:
    client, usuario = _logado()
    id_original = usuario.pk

    resposta = client.patch(
        ME_URL,
        {
            "avatar": "ember",
            "is_staff": True,
            "is_superuser": True,
            "username": "hacker",
            "email": "hacker@exemplo.com",
            "id": str(uuid.uuid4()),
            "password": "outra-senha-123456",
        },
        format="json",
        **csrf_headers(client),
    )

    assert resposta.status_code == 200
    usuario.refresh_from_db()
    assert usuario.pk == id_original
    assert usuario.username == "ana_01"
    assert usuario.email == "ana@exemplo.com"
    assert usuario.is_staff is False
    assert usuario.is_superuser is False
    assert not usuario.check_password("outra-senha-123456")


def test_patch_sem_token_csrf_e_recusado_mesmo_logado() -> None:
    client, usuario = _logado()

    resposta = client.patch(ME_URL, {"avatar": "ember"}, format="json")

    assert resposta.status_code == 403
    usuario.refresh_from_db()
    assert usuario.avatar == "default"
