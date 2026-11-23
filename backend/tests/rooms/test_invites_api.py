"""Contrato da API de convites (PR 2.4): criar, listar, revogar e resgatar."""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from .conftest import (
    JOIN_URL,
    ROOMS_URL,
    convite_url,
    convites_url,
    criar_convite_pela_api,
    criar_sala_pela_api,
    entrar_como_membro,
    logado,
)

pytestmark = pytest.mark.django_db


def _resgatar(usuario: Any, codigo: str) -> Any:
    return logado(usuario).post(JOIN_URL, {"code": codigo}, format="json")


def _promover_a_admin(sala_id: str, usuario: Any) -> None:
    from apps.rooms.models import RoomMember

    RoomMember.objects.filter(room_id=sala_id, user=usuario).update(role="admin")


# --- autenticação -----------------------------------------------------------------------------


def test_anonimo_recebe_401_em_todo_endpoint_de_convite(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    anonimo = APIClient()

    respostas = [
        anonimo.post(convites_url(sala["id"]), {}, format="json"),
        anonimo.get(convites_url(sala["id"])),
        anonimo.delete(convite_url(sala["id"], convite["id"])),
        anonimo.post(JOIN_URL, {"code": convite["code"]}, format="json"),
    ]

    assert [r.status_code in (401, 403) for r in respostas] == [True] * 4


# --- criar ------------------------------------------------------------------------------------


def test_dono_cria_convite_com_o_padrao_de_sete_dias_e_dez_usos(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    dados = criar_convite_pela_api(ana, sala["id"])

    assert dados["max_uses"] == 10
    assert dados["uses"] == 0
    assert len(dados["code"]) >= 22  # 16 bytes em base64 sem preenchimento
    expira = datetime.fromisoformat(dados["expires_at"])
    assert timedelta(days=6, hours=23) < expira - timezone.now() <= timedelta(days=7, minutes=1)


def test_so_o_hash_do_codigo_e_gravado(ana: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)

    dados = criar_convite_pela_api(ana, sala["id"])

    guardado = bytes(RoomInvite.objects.get(id=dados["id"]).code_hash)
    assert guardado == hashlib.sha256(dados["code"].encode()).digest()
    assert dados["code"].encode() not in guardado


def test_dois_convites_tem_codigos_diferentes(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    a = criar_convite_pela_api(ana, sala["id"])
    b = criar_convite_pela_api(ana, sala["id"])

    assert a["code"] != b["code"]


def test_convite_aceita_validade_e_usos_personalizados(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    dados = criar_convite_pela_api(ana, sala["id"], expires_in_days=30, max_uses=50)

    assert dados["max_uses"] == 50
    expira = datetime.fromisoformat(dados["expires_at"])
    assert timedelta(days=29, hours=23) < expira - timezone.now() <= timedelta(days=30, minutes=1)


@pytest.mark.parametrize(
    "corpo",
    [
        {"expires_in_days": 31},
        {"expires_in_days": 0},
        {"expires_in_days": -1},
        {"max_uses": 51},
        {"max_uses": 0},
        {"max_uses": "muitos"},
        {"expires_in_days": 1.5},
    ],
)
def test_politica_fora_dos_limites_da_400_e_nao_cria_nada(ana: Any, corpo: dict[str, Any]) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)

    resposta = logado(ana).post(convites_url(sala["id"]), corpo, format="json")

    assert resposta.status_code == 400
    assert RoomInvite.objects.count() == 0


def test_administrador_cria_convite(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)
    _promover_a_admin(sala["id"], bruno)

    resposta = logado(bruno).post(convites_url(sala["id"]), {}, format="json")

    assert resposta.status_code == 201


def test_membro_comum_nao_cria_convite_403(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)

    resposta = logado(bruno).post(convites_url(sala["id"]), {}, format="json")

    assert resposta.status_code == 403


def test_quem_nao_e_membro_recebe_404_ao_criar_listar_e_revogar(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    de_fora = logado(bruno)

    assert de_fora.post(convites_url(sala["id"]), {}, format="json").status_code == 404
    assert de_fora.get(convites_url(sala["id"])).status_code == 404
    assert de_fora.delete(convite_url(sala["id"], convite["id"])).status_code == 404


def test_limite_de_dez_convites_ativos_por_sala(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    for _ in range(10):
        criar_convite_pela_api(ana, sala["id"])

    resposta = logado(ana).post(convites_url(sala["id"]), {}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "invite_limit_reached"


def test_revogar_libera_uma_vaga_no_limite_de_ativos(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convites = [criar_convite_pela_api(ana, sala["id"]) for _ in range(10)]
    logado(ana).delete(convite_url(sala["id"], convites[0]["id"]))

    resposta = logado(ana).post(convites_url(sala["id"]), {}, format="json")

    assert resposta.status_code == 201


def test_convite_expirado_nao_conta_no_limite_de_ativos(ana: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    for _ in range(10):
        criar_convite_pela_api(ana, sala["id"])
    RoomInvite.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

    resposta = logado(ana).post(convites_url(sala["id"]), {}, format="json")

    assert resposta.status_code == 201


def test_limite_de_convites_e_por_sala(ana: Any) -> None:
    sala_a = criar_sala_pela_api(ana, "A")
    sala_b = criar_sala_pela_api(ana, "B")
    for _ in range(10):
        criar_convite_pela_api(ana, sala_a["id"])

    assert logado(ana).post(convites_url(sala_b["id"]), {}, format="json").status_code == 201


# --- listar e revogar -------------------------------------------------------------------------


def test_listagem_nunca_traz_o_codigo(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    criado = criar_convite_pela_api(ana, sala["id"])

    resposta = logado(ana).get(convites_url(sala["id"]))

    assert resposta.status_code == 200
    itens = resposta.json()
    assert [i["id"] for i in itens] == [criado["id"]]
    assert "code" not in itens[0]
    assert criado["code"] not in resposta.content.decode()


def test_membro_comum_nao_lista_convites_403(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)

    assert logado(bruno).get(convites_url(sala["id"])).status_code == 403


def test_revogar_impede_o_resgate_e_e_idempotente(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    url = convite_url(sala["id"], convite["id"])

    assert logado(ana).delete(url).status_code == 204
    assert logado(ana).delete(url).status_code == 204

    resposta = _resgatar(bruno, convite["code"])
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "invite_revoked"


def test_membro_comum_nao_revoga_403(ana: Any, bruno: Any) -> None:
    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno)
    convite = criar_convite_pela_api(ana, sala["id"])

    resposta = logado(bruno).delete(convite_url(sala["id"], convite["id"]))

    assert resposta.status_code == 403


def test_revogar_convite_de_outra_sala_pela_url_da_minha_da_404(ana: Any, bruno: Any) -> None:
    """Quem administra a sala B não revoga convite da sala A trocando o id na URL."""
    sala_a = criar_sala_pela_api(ana, "A")
    sala_b = criar_sala_pela_api(bruno, "B")
    convite_a = criar_convite_pela_api(ana, sala_a["id"])

    resposta = logado(bruno).delete(convite_url(sala_b["id"], convite_a["id"]))

    assert resposta.status_code == 404
    assert _resgatar(bruno, convite_a["code"]).status_code == 200  # o convite segue válido


# --- resgatar ---------------------------------------------------------------------------------


def test_resgatar_entra_na_sala_como_membro_e_gasta_um_uso(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])

    resposta = _resgatar(bruno, convite["code"])

    assert resposta.status_code == 200
    assert resposta.json()["id"] == sala["id"]
    assert resposta.json()["role"] == "member"
    assert [s["id"] for s in logado(bruno).get(ROOMS_URL).json()] == [sala["id"]]
    assert RoomInvite.objects.get(id=convite["id"]).uses == 1


def test_resgatar_nao_mexe_no_dinheiro(ana: Any, bruno: Any) -> None:
    from apps.economy.models import Wallet, WalletTransaction

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    saldo = Wallet.objects.get(user=bruno).balance
    lancamentos = WalletTransaction.objects.count()

    _resgatar(bruno, convite["code"])

    assert Wallet.objects.get(user=bruno).balance == saldo
    assert WalletTransaction.objects.count() == lancamentos


def test_codigo_desconhecido_da_404_e_nao_gasta_nada(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    criar_convite_pela_api(ana, sala["id"])

    resposta = _resgatar(bruno, "codigo-que-nao-existe")

    assert resposta.status_code == 404
    assert RoomInvite.objects.get().uses == 0


@pytest.mark.parametrize(
    "corpo",
    [{}, {"code": ""}, {"code": "   "}, {"code": 123}, {"code": None}],
)
def test_codigo_ausente_ou_malformado_da_400(bruno: Any, corpo: dict[str, Any]) -> None:
    assert logado(bruno).post(JOIN_URL, corpo, format="json").status_code == 400


def test_convite_expirado_da_409_e_nao_entra(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    RoomInvite.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    resposta = _resgatar(bruno, convite["code"])

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "invite_expired"
    assert logado(bruno).get(ROOMS_URL).json() == []


def test_convite_esgotado_da_409_para_o_proximo(ana: Any, bruno: Any, carla: Any) -> None:
    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"], max_uses=1)
    assert _resgatar(bruno, convite["code"]).status_code == 200

    resposta = _resgatar(carla, convite["code"])

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "invite_exhausted"
    assert logado(carla).get(ROOMS_URL).json() == []


def test_sala_cheia_da_409_e_nao_gasta_uso(ana: Any, bruno: Any, carla: Any) -> None:
    from apps.rooms.models import Room, RoomInvite

    sala = criar_sala_pela_api(ana)
    Room.objects.filter(id=sala["id"]).update(max_members=2)  # a dona + mais um
    convite = criar_convite_pela_api(ana, sala["id"])
    assert _resgatar(bruno, convite["code"]).status_code == 200

    resposta = _resgatar(carla, convite["code"])

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "room_full"
    assert RoomInvite.objects.get().uses == 1


def test_quem_saiu_nao_conta_para_a_sala_cheia(ana: Any, bruno: Any, carla: Any) -> None:
    from apps.rooms.models import Room

    sala = criar_sala_pela_api(ana)
    Room.objects.filter(id=sala["id"]).update(max_members=2)
    entrar_como_membro(sala["id"], bruno, ativo=False)  # status `left`
    convite = criar_convite_pela_api(ana, sala["id"])

    assert _resgatar(carla, convite["code"]).status_code == 200


def test_sala_arquivada_da_409(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import Room

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    Room.objects.filter(id=sala["id"]).update(archived_at=timezone.now())

    resposta = _resgatar(bruno, convite["code"])

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "room_archived"


def test_resgate_repetido_pelo_mesmo_membro_e_idempotente(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomInvite, RoomMember

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"], max_uses=2)

    primeiro = _resgatar(bruno, convite["code"])
    segundo = _resgatar(bruno, convite["code"])

    assert (primeiro.status_code, segundo.status_code) == (200, 200)
    assert RoomInvite.objects.get().uses == 1  # o clique duplo não gasta o segundo uso
    assert RoomMember.objects.filter(room_id=sala["id"], user=bruno).count() == 1


def test_o_dono_resgatando_o_proprio_convite_nao_gasta_uso(ana: Any) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])

    resposta = _resgatar(ana, convite["code"])

    assert resposta.status_code == 200
    assert resposta.json()["role"] == "owner"
    assert RoomInvite.objects.get().uses == 0


def test_quem_saiu_volta_pela_mesma_linha_e_gasta_um_uso(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomInvite, RoomMember

    sala = criar_sala_pela_api(ana)
    entrar_como_membro(sala["id"], bruno, ativo=False)
    convite = criar_convite_pela_api(ana, sala["id"])

    resposta = _resgatar(bruno, convite["code"])

    assert resposta.status_code == 200
    membros = RoomMember.objects.filter(room_id=sala["id"], user=bruno)
    assert [(m.status, m.role) for m in membros] == [("active", "member")]
    assert RoomInvite.objects.get().uses == 1


def test_banido_recebe_404_e_nao_entra(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomInvite, RoomMember

    sala = criar_sala_pela_api(ana)
    RoomMember.objects.create(room_id=sala["id"], user=bruno, role="member", status="banned")
    convite = criar_convite_pela_api(ana, sala["id"])

    resposta = _resgatar(bruno, convite["code"])

    assert resposta.status_code == 404
    assert RoomMember.objects.get(room_id=sala["id"], user=bruno).status == "banned"
    assert RoomInvite.objects.get().uses == 0


def test_o_codigo_nao_aparece_em_respostas_de_erro_nem_em_log(
    ana: Any, bruno: Any, caplog: pytest.LogCaptureFixture
) -> None:
    from apps.rooms.models import RoomInvite

    sala = criar_sala_pela_api(ana)
    convite = criar_convite_pela_api(ana, sala["id"])
    RoomInvite.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    with caplog.at_level(logging.DEBUG):
        resposta = _resgatar(bruno, convite["code"])

    assert resposta.status_code == 409
    assert convite["code"] not in resposta.content.decode()
    assert convite["code"] not in caplog.text


def test_limite_de_tentativas_de_resgate_por_usuario(bruno: Any, carla: Any) -> None:
    """Força bruta: 10 tentativas por minuto por usuário; a 11ª leva 429 (SEGURANCA §5.4)."""
    estados = [_resgatar(bruno, f"palpite-{i}").status_code for i in range(11)]

    assert estados == [404] * 10 + [429]
    assert _resgatar(carla, "palpite-0").status_code == 404  # o limite é por usuário
