"""Lista de membros de uma sala (PR 2.5c1): qualquer membro ATIVO vê; os outros recebem 404."""

import uuid
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from .conftest import (
    ROOMS_URL,
    criar_sala_pela_api,
    entrar_como_membro,
    logado,
    sair_url,
)

pytestmark = pytest.mark.django_db


def membros_url(sala_id: str) -> str:
    return f"{ROOMS_URL}{sala_id}/members/"


def _nomes(usuario: Any, sala_id: str) -> list[str]:
    resposta = logado(usuario).get(membros_url(sala_id))
    assert resposta.status_code == 200, resposta.content
    return [m["username"] for m in resposta.json()]


def test_anonimo_nao_lista_membros(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    assert APIClient().get(membros_url(sala["id"])).status_code in (401, 403)


def test_dono_ve_a_si_mesmo_como_dono(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    resposta = logado(ana).get(membros_url(sala["id"]))

    assert resposta.status_code == 200
    itens = resposta.json()
    assert [(m["username"], m["role"]) for m in itens] == [("ana_01", "owner")]
    assert itens[0]["avatar"] == ana.avatar
    assert itens[0]["joined_at"]


def test_membro_comum_tambem_ve_a_lista_em_ordem_de_entrada(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)

    assert _nomes(bruno, sala["id"]) == ["ana_01", "bruno_02"]
    assert _nomes(ana, sala["id"]) == ["ana_01", "bruno_02"]


def test_administrador_aparece_com_o_papel_certo(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomMember

    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)
    RoomMember.objects.filter(room_id=sala["id"], user=bruno).update(role="admin")

    papeis = {m["username"]: m["role"] for m in logado(ana).get(membros_url(sala["id"])).json()}

    assert papeis == {"ana_01": "owner", "bruno_02": "admin"}


def test_quem_nao_e_membro_recebe_404_igual_ao_de_sala_inexistente(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)

    de_fora = logado(bruno).get(membros_url(sala["id"]))
    inexistente = logado(bruno).get(membros_url(str(uuid.uuid4())))

    assert de_fora.status_code == 404
    assert de_fora.content == inexistente.content


def test_quem_saiu_da_sala_nao_aparece_na_lista(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno, ativo=False)  # status `left`

    assert _nomes(ana, sala["id"]) == ["ana_01"]


def test_quem_saiu_deixa_de_ver_a_lista(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)
    assert _nomes(bruno, sala["id"]) == ["ana_01", "bruno_02"]

    assert logado(bruno).post(sair_url(sala["id"])).status_code == 204

    assert logado(bruno).get(membros_url(sala["id"])).status_code == 404
    assert _nomes(ana, sala["id"]) == ["ana_01"]


def test_banido_nao_aparece_na_lista_nem_a_ve(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomMember

    sala = criar_sala_pela_api(ana)
    RoomMember.objects.create(
        room_id=sala["id"], user=bruno, role="member", status="banned", joined_at=timezone.now()
    )

    assert _nomes(ana, sala["id"]) == ["ana_01"]
    assert logado(bruno).get(membros_url(sala["id"])).status_code == 404


def test_a_lista_nao_expoe_email_nem_id(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    item = logado(ana).get(membros_url(sala["id"])).json()[0]

    assert set(item) == {"username", "avatar", "role", "joined_at"}


def test_so_lista_os_membros_da_propria_sala(ana: Any, bruno: Any) -> None:
    sala_a = criar_sala_pela_api(ana, "A")
    criar_sala_pela_api(bruno, "B")

    assert _nomes(ana, sala_a["id"]) == ["ana_01"]


def test_sala_arquivada_da_404(ana: Any) -> None:
    from apps.rooms.models import Room

    sala = criar_sala_pela_api(ana)
    Room.objects.filter(id=sala["id"]).update(archived_at=timezone.now())

    assert logado(ana).get(membros_url(sala["id"])).status_code == 404


def test_a_lista_so_aceita_leitura(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    assert logado(ana).post(membros_url(sala["id"]), {}, format="json").status_code == 405
    assert logado(ana).delete(membros_url(sala["id"])).status_code == 405
