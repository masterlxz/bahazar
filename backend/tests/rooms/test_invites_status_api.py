"""Campo `status` do convite (PR 2.5c2): o backend decide, com o relógio do servidor."""

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone

from .conftest import (
    JOIN_URL,
    convite_url,
    convites_url,
    criar_convite_pela_api,
    criar_sala_pela_api,
    logado,
)

pytestmark = pytest.mark.django_db

CAMPOS = {"id", "expires_at", "max_uses", "uses", "revoked_at", "created_at", "status"}


def _status_de(usuario: Any, sala_id: str, convite_id: str) -> str:
    itens = logado(usuario).get(convites_url(sala_id)).json()
    return str(next(i["status"] for i in itens if i["id"] == convite_id))


def test_convite_recem_criado_e_ok_na_resposta_e_na_lista(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    criado = criar_convite_pela_api(ana, sala["id"])

    assert criado["status"] == "ok"
    assert _status_de(ana, sala["id"], criado["id"]) == "ok"


def test_a_resposta_de_criacao_tem_o_codigo_e_a_lista_nao(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    criado = criar_convite_pela_api(ana, sala["id"])
    item = logado(ana).get(convites_url(sala["id"])).json()[0]

    assert set(criado) == CAMPOS | {"code"}
    assert set(item) == CAMPOS


def test_revogado(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])

    logado(ana).delete(convite_url(sala["id"], convite["id"]))

    assert _status_de(ana, sala["id"], convite["id"]) == "revoked"


def test_expirado(ana: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    RoomInvite.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    assert _status_de(ana, sala["id"], convite["id"]) == "expired"


def test_esgotado_depois_do_ultimo_uso(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"], max_uses=1)
    assert _status_de(ana, sala["id"], convite["id"]) == "ok"

    assert logado(bruno).post(JOIN_URL, {"code": convite["code"]}, format="json").status_code == 200

    assert _status_de(ana, sala["id"], convite["id"]) == "exhausted"


def test_revogado_vence_expirado_e_esgotado(ana: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"], max_uses=1)
    RoomInvite.objects.update(
        expires_at=timezone.now() - timedelta(days=1), uses=1, revoked_at=timezone.now()
    )

    assert _status_de(ana, sala["id"], convite["id"]) == "revoked"


def test_expirado_vence_esgotado(ana: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"], max_uses=1)
    RoomInvite.objects.update(expires_at=timezone.now() - timedelta(days=1), uses=1)

    assert _status_de(ana, sala["id"], convite["id"]) == "expired"


def test_a_lista_traz_todos_do_mais_novo_ao_mais_antigo_cada_um_com_seu_estado(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    antigo = criar_convite_pela_api(ana, sala["id"])
    novo = criar_convite_pela_api(ana, sala["id"])
    logado(ana).delete(convite_url(sala["id"], antigo["id"]))

    itens = logado(ana).get(convites_url(sala["id"])).json()

    assert [(i["id"], i["status"]) for i in itens] == [
        (novo["id"], "ok"),
        (antigo["id"], "revoked"),
    ]
