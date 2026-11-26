"""Vitrine × bloqueio (ADR 0017): o bloqueio muda só a vista de quem bloqueou.

Quem bloqueou não vê os anúncios de quem bloqueou. O bloqueado vê tudo igual e não aprende que
foi bloqueado (a mesma regra de `friends.selectors.blocked_by`).
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.friends import services as friends

from .conftest import LISTINGS_URL, logado

pytestmark = pytest.mark.django_db


def _anunciar(cliente: APIClient, instancia: Any) -> str:
    resposta = cliente.post(
        LISTINGS_URL, {"instance_id": str(instancia.pk), "price": 1000}, format="json"
    )
    assert resposta.status_code == 201, resposta.content
    return str(resposta.json()["id"])


def _ids_da_vitrine(cliente: APIClient) -> list[str]:
    resposta = cliente.get(LISTINGS_URL)
    assert resposta.status_code == 200
    return [a["id"] for a in resposta.json()["results"]]


@pytest.fixture
def anuncios(cena: SimpleNamespace) -> SimpleNamespace:
    """Um anúncio de cada: ana (a1), bruno (b1) e carla (c1)."""
    return SimpleNamespace(
        ana=_anunciar(logado(cena.ana), cena.a1),
        bruno=_anunciar(logado(cena.bruno), cena.b1),
        carla=_anunciar(logado(cena.carla), cena.c1),
    )


def test_quem_bloqueou_nao_ve_os_anuncios_de_quem_bloqueou(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    friends.block(cena.ana, cena.bruno.username)

    resposta = logado(cena.ana).get(LISTINGS_URL)

    assert resposta.status_code == 200
    assert resposta.json()["count"] == 2
    assert set(_ids_da_vitrine(logado(cena.ana))) == {anuncios.ana, anuncios.carla}


def test_o_detalhe_do_anuncio_de_quem_bloqueei_da_404_igual_ao_de_anuncio_inexistente(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    friends.block(cena.ana, cena.bruno.username)
    ana = logado(cena.ana)

    escondido = ana.get(f"{LISTINGS_URL}{anuncios.bruno}/")
    inexistente = ana.get(f"{LISTINGS_URL}{uuid.uuid4()}/")

    assert escondido.status_code == 404
    assert escondido.json() == inexistente.json()


def test_o_bloqueado_ve_a_vitrine_de_antes_e_nao_percebe_o_bloqueio(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    bruno = logado(cena.bruno)
    antes = _ids_da_vitrine(bruno)

    friends.block(cena.ana, cena.bruno.username)

    assert _ids_da_vitrine(bruno) == antes
    assert anuncios.ana in antes
    assert bruno.get(f"{LISTINGS_URL}{anuncios.ana}/").status_code == 200


def test_o_bloqueio_no_sentido_inverso_nao_esconde_nada_de_quem_foi_bloqueado(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    """bruno bloqueou ana: ana (a bloqueada) continua vendo os anúncios de bruno."""
    friends.block(cena.bruno, cena.ana.username)
    ana = logado(cena.ana)

    assert anuncios.bruno in _ids_da_vitrine(ana)
    assert ana.get(f"{LISTINGS_URL}{anuncios.bruno}/").status_code == 200


def test_desbloquear_traz_os_anuncios_de_volta(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    friends.block(cena.ana, cena.bruno.username)
    assert anuncios.bruno not in _ids_da_vitrine(logado(cena.ana))

    friends.unblock(cena.ana, cena.bruno.username)

    assert anuncios.bruno in _ids_da_vitrine(logado(cena.ana))


def test_amigo_aceito_e_pedido_pendente_nao_escondem_nada(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    """ana e bruno são amigos aceitos; ana pediu amizade a carla (pendente)."""
    friends.send_request(cena.ana, cena.carla.username)

    assert set(_ids_da_vitrine(logado(cena.ana))) == {
        anuncios.ana,
        anuncios.bruno,
        anuncios.carla,
    }


def test_o_proprio_anuncio_continua_aparecendo_para_quem_bloqueou(
    cena: SimpleNamespace, anuncios: SimpleNamespace
) -> None:
    friends.block(cena.ana, cena.bruno.username)

    assert anuncios.ana in _ids_da_vitrine(logado(cena.ana))
