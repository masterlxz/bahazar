"""A permissão central de visibilidade (R1): dono e amigo veem; o resto recebe 404.

`can_view` é a única função que os endpoints futuros (inventário, trocas) vão consultar. O
perfil `GET /friends/<username>/` é o primeiro consumidor e fixa o contrato do 404.
"""

from typing import Any

import pytest

from apps.friends import selectors

from .conftest import bloqueio_url, logado, pedir, perfil_url, tornar_amigos

pytestmark = pytest.mark.django_db


# --- selector -------------------------------------------------------------------------------


def test_can_view_dono_ve_a_si_mesmo(ana: Any) -> None:
    assert selectors.can_view(ana, ana) is True


def test_can_view_sem_relacao_nega(ana: Any, bruno: Any) -> None:
    assert selectors.can_view(ana, bruno) is False


def test_can_view_pedido_pendente_nega_nos_dois_sentidos(ana: Any, bruno: Any) -> None:
    pedir(ana, bruno)

    assert selectors.can_view(ana, bruno) is False
    assert selectors.can_view(bruno, ana) is False


def test_can_view_amigo_aceito_ve_nos_dois_sentidos(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)

    assert selectors.can_view(ana, bruno) is True
    assert selectors.can_view(bruno, ana) is True


def test_can_view_bloqueado_nega_nos_dois_sentidos(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)
    logado(ana).post(bloqueio_url("bruno_02"))

    assert selectors.can_view(ana, bruno) is False
    assert selectors.can_view(bruno, ana) is False


def test_can_view_nao_vaza_amizade_de_terceiros(ana: Any, bruno: Any, carla: Any) -> None:
    """ana e bruno são amigos; carla não ganha visão de nenhum dos dois."""
    tornar_amigos(ana, bruno)

    assert selectors.can_view(carla, ana) is False
    assert selectors.can_view(carla, bruno) is False


def test_friends_of_lista_so_amigos_aceitos(ana: Any, bruno: Any, carla: Any) -> None:
    tornar_amigos(ana, bruno)
    pedir(carla, ana)  # pendente: não conta

    assert [u.username for u in selectors.friends_of(ana)] == ["bruno_02"]


# --- contrato do 404 no endpoint de perfil --------------------------------------------------


def test_amigo_ve_o_perfil(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)

    resposta = logado(ana).get(perfil_url("bruno_02"))

    assert resposta.status_code == 200
    assert resposta.json() == {"username": "bruno_02", "avatar": bruno.avatar}


def test_perfil_nao_expoe_email_nem_id(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)

    dados = logado(ana).get(perfil_url("bruno_02")).json()

    assert set(dados) == {"username", "avatar"}


def test_dono_ve_o_proprio_perfil(ana: Any) -> None:
    assert logado(ana).get(perfil_url("ana_01")).status_code == 200


def _cenario_sem_relacao(ana: Any, bruno: Any) -> None:
    return None


def _cenario_pendente(ana: Any, bruno: Any) -> None:
    pedir(ana, bruno)


def _cenario_bloqueado_por_mim(ana: Any, bruno: Any) -> None:
    logado(ana).post(bloqueio_url("bruno_02"))


def _cenario_bloqueado_por_ele(ana: Any, bruno: Any) -> None:
    logado(bruno).post(bloqueio_url("ana_01"))


def _cenario_ex_amigo(ana: Any, bruno: Any) -> None:
    tornar_amigos(ana, bruno)
    logado(ana).delete(perfil_url("bruno_02"))


@pytest.mark.parametrize(
    "cenario",
    [
        _cenario_sem_relacao,
        _cenario_pendente,
        _cenario_bloqueado_por_mim,
        _cenario_bloqueado_por_ele,
        _cenario_ex_amigo,
    ],
)
def test_quem_nao_e_amigo_recebe_404_igual_ao_de_inexistente(
    ana: Any, bruno: Any, cenario: Any
) -> None:
    cenario(ana, bruno)

    sem_acesso = logado(ana).get(perfil_url("bruno_02"))
    inexistente = logado(ana).get(perfil_url("ninguem_99"))

    assert sem_acesso.status_code == 404
    assert sem_acesso.content == inexistente.content
