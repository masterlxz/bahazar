"""Quem pode ver o inventário de quem (PR 3.2b). A decisão é só `friends.selectors.can_view`.

Dono e amigo aceito veem; todo o resto (sem relação, pedido pendente, bloqueio nos dois
sentidos, usuário inexistente) recebe o MESMO 404: 403 confirmaria que o jogador existe.
"""

from typing import Any

import pytest

from .conftest import (
    INVENTORY_URL,
    bloquear,
    criar_instancia,
    logado,
    pedir_amizade,
    tornar_amigos,
    url_de,
)

pytestmark = pytest.mark.django_db


def _ids(resposta: Any) -> list[str]:
    return [item["id"] for item in resposta.json()["results"]]


def test_amigo_ve_o_inventario_do_outro_nos_dois_sentidos(ana: Any, bruno: Any, skin: Any) -> None:
    da_ana = criar_instancia(ana, skin)
    do_bruno = criar_instancia(bruno, skin)
    tornar_amigos(ana, bruno)

    vendo_bruno = logado(ana).get(url_de("bruno_02"))
    vendo_ana = logado(bruno).get(url_de("ana_01"))

    assert vendo_bruno.status_code == 200
    assert _ids(vendo_bruno) == [str(do_bruno.id)]  # só os dele, nunca os de quem pediu
    assert vendo_ana.status_code == 200
    assert _ids(vendo_ana) == [str(da_ana.id)]


def test_sem_relacao_recebe_404(ana: Any, bruno: Any, skin: Any) -> None:
    criar_instancia(bruno, skin)

    assert logado(ana).get(url_de("bruno_02")).status_code == 404


def test_pedido_pendente_nao_da_visao_em_nenhum_sentido(ana: Any, bruno: Any, skin: Any) -> None:
    criar_instancia(ana, skin)
    criar_instancia(bruno, skin)
    pedir_amizade(ana, bruno)

    assert logado(ana).get(url_de("bruno_02")).status_code == 404
    assert logado(bruno).get(url_de("ana_01")).status_code == 404


def test_bloqueio_tira_a_visao_nos_dois_sentidos(ana: Any, bruno: Any, skin: Any) -> None:
    criar_instancia(ana, skin)
    criar_instancia(bruno, skin)
    bloquear(ana, bruno)

    assert logado(ana).get(url_de("bruno_02")).status_code == 404  # quem bloqueou
    assert logado(bruno).get(url_de("ana_01")).status_code == 404  # quem foi bloqueado


def test_amizade_desfeita_volta_a_dar_404(ana: Any, bruno: Any, skin: Any) -> None:
    from apps.friends.models import Friendship

    criar_instancia(bruno, skin)
    tornar_amigos(ana, bruno)
    assert logado(ana).get(url_de("bruno_02")).status_code == 200

    Friendship.objects.all().delete()

    assert logado(ana).get(url_de("bruno_02")).status_code == 404


def test_amizade_de_terceiros_nao_da_visao_a_ninguem(
    ana: Any, bruno: Any, carla: Any, skin: Any
) -> None:
    criar_instancia(ana, skin)
    criar_instancia(bruno, skin)
    tornar_amigos(ana, bruno)

    assert logado(carla).get(url_de("ana_01")).status_code == 404
    assert logado(carla).get(url_de("bruno_02")).status_code == 404


def test_o_404_de_quem_nao_pode_ver_e_identico_ao_de_usuario_inexistente(
    ana: Any, bruno: Any, skin: Any
) -> None:
    """Mesmo status, mesmo corpo e mesmo tipo de conteúdo: nada denuncia que o jogador existe."""
    criar_instancia(bruno, skin)
    cliente = logado(ana)

    nao_amigo = cliente.get(url_de("bruno_02"))
    inexistente = cliente.get(url_de("fantasma_99"))

    assert nao_amigo.status_code == inexistente.status_code == 404
    assert nao_amigo.content == inexistente.content
    assert nao_amigo["Content-Type"] == inexistente["Content-Type"]


def test_autoriza_antes_de_validar_a_query(ana: Any, bruno: Any, skin: Any) -> None:
    """Query inválida de quem não pode ver dá 404 (não 400): o status não denuncia a amizade."""
    criar_instancia(bruno, skin)
    invalida = {"ordering": "inventado", "wear": "inventado", "page_size": "0"}

    assert logado(ana).get(url_de("bruno_02"), invalida).status_code == 404
    assert logado(ana).get(url_de("fantasma_99"), invalida).status_code == 404

    tornar_amigos(ana, bruno)

    assert logado(ana).get(url_de("bruno_02"), invalida).status_code == 400  # quem pode ver
    assert logado(ana).get(INVENTORY_URL, invalida).status_code == 400  # o dono


def test_username_com_caixa_alta_resolve_o_mesmo_jogador(ana: Any, bruno: Any, skin: Any) -> None:
    criar_instancia(bruno, skin)
    tornar_amigos(ana, bruno)

    assert logado(ana).get(url_de("BRUNO_02")).status_code == 200
