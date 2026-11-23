"""Contrato da API de salas (PR 2.1): criar, listar, ler, renomear, sair e isolamento."""

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

from .conftest import (
    ROOMS_URL,
    criar_sala_pela_api,
    criar_usuario,
    detalhe_url,
    logado,
    sair_url,
)

pytestmark = pytest.mark.django_db

ID_INEXISTENTE = str(uuid.uuid4())


def _promover_a_membro(sala_id: str, usuario: Any) -> None:
    """Põe `usuario` na sala como membro comum. Atalho de cenário: não passa por convite."""
    from apps.rooms.models import RoomMember

    RoomMember.objects.create(room_id=sala_id, user=usuario, role="member", status="active")


# --- autenticação -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "montar_url"),
    [
        ("get", lambda sala: ROOMS_URL),
        ("post", lambda sala: ROOMS_URL),
        ("get", lambda sala: detalhe_url(sala)),
        ("patch", lambda sala: detalhe_url(sala)),
        ("post", lambda sala: sair_url(sala)),
    ],
)
def test_anonimo_recebe_401_em_todo_endpoint_de_sala(
    metodo: str, montar_url: Any, ana: Any
) -> None:
    sala = criar_sala_pela_api(ana)

    resposta = getattr(APIClient(), metodo)(montar_url(sala["id"]), {}, format="json")

    assert resposta.status_code in (401, 403)


# --- criar ------------------------------------------------------------------------------------


def test_criar_sala_torna_o_criador_dono_e_a_sala_privada(ana: Any) -> None:
    resposta = logado(ana).post(ROOMS_URL, {"name": "Amigos"}, format="json")

    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["name"] == "Amigos"
    assert dados["visibility"] == "private"
    assert dados["role"] == "owner"
    assert dados["max_members"] == 20


@pytest.mark.parametrize("nome", ["", "   ", "x" * 200])
def test_nome_invalido_da_400_e_nao_grava_nada(nome: str, ana: Any) -> None:
    from apps.rooms.models import Room

    resposta = logado(ana).post(ROOMS_URL, {"name": nome}, format="json")

    assert resposta.status_code == 400
    assert Room.objects.count() == 0


def test_campos_sensiveis_no_corpo_sao_ignorados_ao_criar(ana: Any, bruno: Any) -> None:
    corpo = {
        "name": "Amigos",
        "visibility": "public",
        "owner": str(bruno.id),
        "role": "member",
        "max_members": 9999,
    }

    resposta = logado(ana).post(ROOMS_URL, corpo, format="json")

    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["visibility"] == "private"
    assert dados["role"] == "owner"
    assert dados["max_members"] == 20
    from apps.rooms.models import Room

    assert str(Room.objects.get(id=dados["id"]).owner_id) == str(ana.id)


def test_limite_de_cinco_salas_como_dono(ana: Any) -> None:
    for i in range(5):
        criar_sala_pela_api(ana, f"Sala {i}")

    resposta = logado(ana).post(ROOMS_URL, {"name": "Sala 6"}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "room_limit_reached"


# --- listar e ler -----------------------------------------------------------------------------


def test_listar_mostra_so_as_salas_onde_o_usuario_e_membro(ana: Any, bruno: Any) -> None:
    da_ana = criar_sala_pela_api(ana, "Da Ana")
    criar_sala_pela_api(bruno, "Do Bruno")

    resposta = logado(ana).get(ROOMS_URL)

    assert resposta.status_code == 200
    assert [s["id"] for s in resposta.json()] == [da_ana["id"]]


def test_sala_arquivada_nao_aparece_na_listagem(ana: Any) -> None:
    from django.utils import timezone

    from apps.rooms.models import Room

    sala = criar_sala_pela_api(ana)
    Room.objects.filter(id=sala["id"]).update(archived_at=timezone.now())

    resposta = logado(ana).get(ROOMS_URL)

    assert resposta.json() == []


def test_membro_le_o_detalhe_da_propria_sala(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    resposta = logado(ana).get(detalhe_url(sala["id"]))

    assert resposta.status_code == 200
    assert resposta.json()["id"] == sala["id"]


# --- isolamento entre salas (IDOR) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "montar_url"),
    [
        ("get", detalhe_url),
        ("patch", detalhe_url),
        ("post", sair_url),
    ],
)
def test_usuario_de_outra_sala_recebe_404_igual_a_sala_inexistente(
    metodo: str, montar_url: Any, ana: Any, bruno: Any
) -> None:
    sala_da_ana = criar_sala_pela_api(ana)
    corpo = {"name": "Invadida"}

    de_fora = getattr(logado(bruno), metodo)(montar_url(sala_da_ana["id"]), corpo, format="json")
    inexistente = getattr(logado(bruno), metodo)(montar_url(ID_INEXISTENTE), corpo, format="json")

    assert de_fora.status_code == 404
    assert inexistente.status_code == 404
    assert de_fora.content == inexistente.content


# --- permissões de admin ----------------------------------------------------------------------


def test_membro_comum_nao_renomeia_a_sala(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    _promover_a_membro(sala["id"], bruno)

    resposta = logado(bruno).patch(detalhe_url(sala["id"]), {"name": "Golpe"}, format="json")

    assert resposta.status_code == 403


def test_dono_renomeia_a_sala(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    resposta = logado(ana).patch(detalhe_url(sala["id"]), {"name": "Novo nome"}, format="json")

    assert resposta.status_code == 200
    assert resposta.json()["name"] == "Novo nome"


def test_patch_ignora_dono_visibilidade_e_limite_de_membros(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import Room

    sala = criar_sala_pela_api(ana)
    corpo = {"name": "Novo", "owner": str(bruno.id), "visibility": "public", "max_members": 999}

    resposta = logado(ana).patch(detalhe_url(sala["id"]), corpo, format="json")

    assert resposta.status_code == 200
    guardada = Room.objects.get(id=sala["id"])
    assert guardada.name == "Novo"
    assert str(guardada.owner_id) == str(ana.id)
    assert guardada.visibility == "private"
    assert guardada.max_members == 20


# --- sair -------------------------------------------------------------------------------------


def test_membro_comum_sai_e_a_sala_some_para_ele(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    _promover_a_membro(sala["id"], bruno)

    saiu = logado(bruno).post(sair_url(sala["id"]))

    assert saiu.status_code == 204
    assert logado(bruno).get(ROOMS_URL).json() == []
    assert logado(bruno).get(detalhe_url(sala["id"])).status_code == 404


def test_dono_nao_pode_sair_da_propria_sala(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    resposta = logado(ana).post(sair_url(sala["id"]))

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "owner_cannot_leave"
    assert logado(ana).get(detalhe_url(sala["id"])).status_code == 200


def test_outro_usuario_continua_sem_acesso_depois_de_sair(ana: Any) -> None:
    carla = criar_usuario("carla_03")
    sala = criar_sala_pela_api(ana)
    _promover_a_membro(sala["id"], carla)
    logado(carla).post(sair_url(sala["id"]))

    resposta = logado(carla).post(sair_url(sala["id"]))

    assert resposta.status_code == 404
