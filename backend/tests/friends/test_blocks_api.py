"""Listagem de bloqueados (PR 2.5b): só quem EU bloqueei, nunca quem me bloqueou (privacidade)."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from .conftest import bloqueio_url, logado, pedir, perfil_url, tornar_amigos

pytestmark = pytest.mark.django_db

BLOCKS_URL = "/api/v1/blocks/"


def _nomes(usuario: Any) -> list[str]:
    resposta = logado(usuario).get(BLOCKS_URL)
    assert resposta.status_code == 200, resposta.content
    return [item["username"] for item in resposta.json()]


def test_anonimo_nao_lista_bloqueados() -> None:
    assert APIClient().get(BLOCKS_URL).status_code in (401, 403)


def test_sem_bloqueios_a_lista_e_vazia(ana: Any) -> None:
    assert logado(ana).get(BLOCKS_URL).json() == []


def test_lista_quem_eu_bloqueei_em_ordem_de_username(ana: Any, bruno: Any, carla: Any) -> None:
    logado(ana).post(bloqueio_url("carla_03"))
    logado(ana).post(bloqueio_url("bruno_02"))

    resposta = logado(ana).get(BLOCKS_URL)

    assert resposta.status_code == 200
    assert resposta.json() == [
        {"username": "bruno_02", "avatar": bruno.avatar},
        {"username": "carla_03", "avatar": carla.avatar},
    ]


def test_nao_lista_quem_me_bloqueou(ana: Any, bruno: Any) -> None:
    """Se bruno bloqueou ana, a lista da ana continua vazia: ela não pode saber quem a bloqueou."""
    logado(bruno).post(bloqueio_url("ana_01"))

    assert _nomes(ana) == []
    assert _nomes(bruno) == ["ana_01"]


def test_nao_lista_amigos_nem_pedidos_pendentes(ana: Any, bruno: Any, carla: Any) -> None:
    tornar_amigos(ana, bruno)
    pedir(ana, carla)

    assert _nomes(ana) == []


def test_bloquear_um_amigo_o_move_para_a_lista(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)

    logado(ana).post(bloqueio_url("bruno_02"))

    assert _nomes(ana) == ["bruno_02"]


def test_desbloquear_tira_da_lista(ana: Any, bruno: Any) -> None:
    logado(ana).post(bloqueio_url("bruno_02"))

    logado(ana).delete(bloqueio_url("bruno_02"))

    assert _nomes(ana) == []


def test_bloqueio_do_outro_lado_nao_e_roubado_por_um_segundo_bloqueio(
    ana: Any, bruno: Any
) -> None:
    """bruno bloqueou ana primeiro; ana bloquear bruno por cima não entra na lista dela."""
    logado(bruno).post(bloqueio_url("ana_01"))
    logado(ana).post(bloqueio_url("bruno_02"))

    assert _nomes(ana) == []
    assert _nomes(bruno) == ["ana_01"]


def test_a_lista_nao_expoe_email_nem_id(ana: Any, bruno: Any) -> None:
    logado(ana).post(bloqueio_url("bruno_02"))

    item = logado(ana).get(BLOCKS_URL).json()[0]

    assert set(item) == {"username", "avatar"}


def test_bloqueado_continua_dando_404_no_perfil(ana: Any, bruno: Any) -> None:
    logado(ana).post(bloqueio_url("bruno_02"))

    assert logado(ana).get(perfil_url("bruno_02")).status_code == 404


def test_a_lista_so_aceita_leitura(ana: Any) -> None:
    assert logado(ana).post(BLOCKS_URL, {}, format="json").status_code == 405
    assert logado(ana).delete(BLOCKS_URL).status_code == 405
