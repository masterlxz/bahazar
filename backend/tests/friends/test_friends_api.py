"""Fluxo de amizade pela API: pedir, aceitar, recusar, remover, bloquear."""

from typing import Any

import pytest

from .conftest import (
    FRIENDS_URL,
    REQUESTS_URL,
    SENT_URL,
    aceitar_url,
    bloqueio_url,
    logado,
    pedir,
    perfil_url,
    recusar_url,
    tornar_amigos,
)

pytestmark = pytest.mark.django_db


def _nomes(resposta: Any) -> list[str]:
    return [item["username"] for item in resposta.json()]


# --- autenticação ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [FRIENDS_URL, REQUESTS_URL, SENT_URL])
def test_listas_exigem_login(url: str) -> None:
    from rest_framework.test import APIClient

    assert APIClient().get(url).status_code in (401, 403)


# --- pedir ----------------------------------------------------------------------------------


def test_pedir_cria_pedido_pendente_visivel_aos_dois_lados(ana: Any, bruno: Any) -> None:
    pedido = pedir(ana, bruno)

    assert pedido["requester"] == "ana_01"
    assert pedido["addressee"] == "bruno_02"
    assert pedido["status"] == "pending"
    recebidos = logado(bruno).get(REQUESTS_URL).json()
    enviados = logado(ana).get(SENT_URL).json()
    assert [p["id"] for p in recebidos] == [pedido["id"]]
    assert [p["id"] for p in enviados] == [pedido["id"]]
    assert logado(ana).get(REQUESTS_URL).json() == []  # quem pediu não "recebeu" nada


def test_pedir_a_si_mesmo_e_recusado(ana: Any) -> None:
    resposta = logado(ana).post(REQUESTS_URL, {"username": "ana_01"}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "friendship_unavailable"


def test_pedir_a_usuario_inexistente_e_igual_a_bloqueado(ana: Any, bruno: Any) -> None:
    """Anti-enumeração: inexistente e "me bloqueou" dão a MESMA resposta."""
    logado(bruno).post(f"/api/v1/friends/{ana.username}/block/")
    # bruno bloqueou ana: ana não pode pedir
    bloqueado = logado(ana).post(REQUESTS_URL, {"username": "bruno_02"}, format="json")
    inexistente = logado(ana).post(REQUESTS_URL, {"username": "ninguem_99"}, format="json")

    assert bloqueado.status_code == inexistente.status_code == 409
    assert bloqueado.json() == inexistente.json()
    assert bloqueado.json()["code"] == "friendship_unavailable"


def test_pedido_repetido_e_recusado(ana: Any, bruno: Any) -> None:
    pedir(ana, bruno)

    resposta = logado(ana).post(REQUESTS_URL, {"username": "bruno_02"}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "already_pending"


def test_pedir_a_quem_ja_te_pediu_nao_aceita_sozinho(ana: Any, bruno: Any) -> None:
    pedir(ana, bruno)

    resposta = logado(bruno).post(REQUESTS_URL, {"username": "ana_01"}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "already_pending"
    assert logado(bruno).get(FRIENDS_URL).json() == []  # continuam sem ser amigos


def test_pedir_a_quem_ja_e_amigo_e_recusado(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)

    resposta = logado(ana).post(REQUESTS_URL, {"username": "bruno_02"}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "already_friends"


def test_pedido_sem_username_e_400(ana: Any) -> None:
    assert logado(ana).post(REQUESTS_URL, {}, format="json").status_code == 400


# --- aceitar e recusar ----------------------------------------------------------------------


def test_aceitar_torna_amigos_dos_dois_lados(ana: Any, bruno: Any) -> None:
    pedido = pedir(ana, bruno)

    resposta = logado(bruno).post(aceitar_url(pedido["id"]))

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "accepted"
    assert _nomes(logado(ana).get(FRIENDS_URL)) == ["bruno_02"]
    assert _nomes(logado(bruno).get(FRIENDS_URL)) == ["ana_01"]
    assert logado(bruno).get(REQUESTS_URL).json() == []  # saiu da lista de pendentes


def test_so_o_destinatario_aceita(ana: Any, bruno: Any, carla: Any) -> None:
    pedido = pedir(ana, bruno)

    # quem pediu, e um terceiro, recebem 404 (não revela que o pedido existe)
    assert logado(ana).post(aceitar_url(pedido["id"])).status_code == 404
    assert logado(carla).post(aceitar_url(pedido["id"])).status_code == 404
    assert logado(bruno).get(FRIENDS_URL).json() == []


def test_aceitar_duas_vezes_da_404_na_segunda(ana: Any, bruno: Any) -> None:
    pedido = pedir(ana, bruno)
    logado(bruno).post(aceitar_url(pedido["id"]))

    assert logado(bruno).post(aceitar_url(pedido["id"])).status_code == 404


def test_recusar_apaga_o_pedido_e_permite_pedir_de_novo(ana: Any, bruno: Any) -> None:
    pedido = pedir(ana, bruno)

    resposta = logado(bruno).post(recusar_url(pedido["id"]))

    assert resposta.status_code == 204
    assert logado(bruno).get(REQUESTS_URL).json() == []
    assert logado(ana).get(SENT_URL).json() == []
    pedir(ana, bruno)  # não levanta: a recusa não deixa rastro que bloqueie


def test_so_o_destinatario_recusa(ana: Any, bruno: Any) -> None:
    pedido = pedir(ana, bruno)

    assert logado(ana).post(recusar_url(pedido["id"])).status_code == 404
    assert len(logado(bruno).get(REQUESTS_URL).json()) == 1


# --- remover amigo --------------------------------------------------------------------------


@pytest.mark.parametrize("quem_remove", ["ana_01", "bruno_02"])
def test_qualquer_dos_dois_remove_a_amizade(ana: Any, bruno: Any, quem_remove: str) -> None:
    tornar_amigos(ana, bruno)
    remove, outro = (ana, bruno) if quem_remove == "ana_01" else (bruno, ana)

    resposta = logado(remove).delete(perfil_url(outro.username))

    assert resposta.status_code == 204
    assert logado(ana).get(FRIENDS_URL).json() == []
    assert logado(bruno).get(FRIENDS_URL).json() == []


def test_remover_quem_nao_e_amigo_da_404(ana: Any, bruno: Any) -> None:
    assert logado(ana).delete(perfil_url("bruno_02")).status_code == 404


def test_remover_nao_apaga_um_pedido_pendente(ana: Any, bruno: Any) -> None:
    """DELETE /friends/<u>/ só remove amizade aceita; pedido pendente se trata como pedido."""
    pedir(ana, bruno)

    assert logado(ana).delete(perfil_url("bruno_02")).status_code == 404
    assert len(logado(bruno).get(REQUESTS_URL).json()) == 1


# --- bloquear -------------------------------------------------------------------------------


def test_bloquear_sem_relacao_previa_cria_o_bloqueio(ana: Any, bruno: Any) -> None:
    assert logado(ana).post(bloqueio_url("bruno_02")).status_code == 204

    resposta = logado(bruno).post(REQUESTS_URL, {"username": "ana_01"}, format="json")
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "friendship_unavailable"


def test_bloquear_um_amigo_derruba_a_amizade(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)

    assert logado(ana).post(bloqueio_url("bruno_02")).status_code == 204

    assert logado(ana).get(FRIENDS_URL).json() == []
    assert logado(bruno).get(FRIENDS_URL).json() == []


def test_bloquear_cancela_pedido_pendente_dos_dois_sentidos(ana: Any, bruno: Any) -> None:
    pedido = pedir(bruno, ana)

    logado(ana).post(bloqueio_url("bruno_02"))

    assert logado(ana).get(REQUESTS_URL).json() == []
    assert logado(ana).post(aceitar_url(pedido["id"])).status_code == 404


def test_bloquear_duas_vezes_e_idempotente(ana: Any, bruno: Any) -> None:
    assert logado(ana).post(bloqueio_url("bruno_02")).status_code == 204
    assert logado(ana).post(bloqueio_url("bruno_02")).status_code == 204


def test_bloquear_a_si_mesmo_ou_inexistente_da_404(ana: Any) -> None:
    assert logado(ana).post(bloqueio_url("ana_01")).status_code == 404
    assert logado(ana).post(bloqueio_url("ninguem_99")).status_code == 404


def test_bloquear_quem_ja_te_bloqueou_nao_rouba_o_bloqueio(ana: Any, bruno: Any) -> None:
    """Se bruno já bloqueou ana, o bloqueio de ana por cima não pode tirar o dele."""
    logado(bruno).post(bloqueio_url("ana_01"))

    logado(ana).post(bloqueio_url("bruno_02"))

    # ana desbloquear NÃO libera: o bloqueio que sobra é o do bruno
    logado(ana).delete(bloqueio_url("bruno_02"))
    resposta = logado(ana).post(REQUESTS_URL, {"username": "bruno_02"}, format="json")
    assert resposta.status_code == 409


def test_so_o_bloqueador_desbloqueia(ana: Any, bruno: Any) -> None:
    logado(ana).post(bloqueio_url("bruno_02"))

    # o bloqueado não consegue desfazer: 404, e o bloqueio continua
    assert logado(bruno).delete(bloqueio_url("ana_01")).status_code == 404
    assert logado(bruno).post(REQUESTS_URL, {"username": "ana_01"}, format="json").status_code == 409

    assert logado(ana).delete(bloqueio_url("bruno_02")).status_code == 204
    pedir(bruno, ana)  # liberado


def test_desbloquear_nao_restaura_a_amizade(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)
    logado(ana).post(bloqueio_url("bruno_02"))

    logado(ana).delete(bloqueio_url("bruno_02"))

    assert logado(ana).get(FRIENDS_URL).json() == []


def test_o_bloqueador_nao_pode_pedir_amizade_ao_bloqueado(ana: Any, bruno: Any) -> None:
    logado(ana).post(bloqueio_url("bruno_02"))

    resposta = logado(ana).post(REQUESTS_URL, {"username": "bruno_02"}, format="json")

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "friendship_unavailable"
