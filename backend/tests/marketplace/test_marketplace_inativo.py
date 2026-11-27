"""Mercado com um jogador desativado (`is_active=False`): J4.

Decisões do dono (2026-11-27): o COMPRADOR desativado recebe 409 `player_unavailable` (ele é o
ator, a resposta só fala dele). O anúncio do VENDEDOR desativado some da vitrine e do detalhe
(404, como o de anúncio inexistente), e a COMPRA dá o mesmo 409 `listing_not_active` de um
anúncio fechado, em qualquer estado dele: quem raspou a vitrine só pode pedir a compra de um `id`
visto, e esse `id` não pode denunciar a conta desativada (decisão do dono, 2026-11-27, depois do
revisor mostrar que o 404 distinguia desativado de fechado).
O jogador é desativado direto no banco (`.update`), de propósito: os objetos `User` em memória
seguem com `is_active=True`, então só uma leitura do banco, sob a trava dos jogadores, passa.
Saldo inicial 2.500 (`economy.rules.STARTING_BALANCE`); taxa de 5% (hipótese do dono).
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.economy.audit import check_ledger
from apps.economy.models import Wallet
from apps.friends import services as friends
from apps.inventory.models import SkinInstance
from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketTransaction

from .conftest import LISTINGS_URL, anunciar, logado, nova_chave

pytestmark = pytest.mark.django_db

CODE = "player_unavailable"
SALDO_INICIAL = 2_500
User: Any = get_user_model()


def _desativar(usuario: Any) -> None:
    User.objects.filter(pk=usuario.pk).update(is_active=False)


def _reativar(usuario: Any) -> None:
    User.objects.filter(pk=usuario.pk).update(is_active=True)


def _comprar(cliente: APIClient, listing_id: Any, chave: str | None = None) -> Any:
    return cliente.post(
        f"{LISTINGS_URL}{listing_id}/buy/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=chave or nova_chave(),
    )


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def _nada_mudou(cena: SimpleNamespace, anuncio: Any) -> None:
    assert SkinInstance.objects.get(pk=anuncio.instance_id).owner_id == cena.ana.pk
    anuncio.refresh_from_db()
    assert (anuncio.status, anuncio.closed_at) == (ListingStatus.ACTIVE, None)
    assert MarketTransaction.objects.count() == 0
    assert (_saldo(cena.bruno), _saldo(cena.ana)) == (SALDO_INICIAL, SALDO_INICIAL)
    assert check_ledger() == []


def _ids_da_vitrine(cliente: APIClient) -> set[str]:
    resposta = cliente.get(LISTINGS_URL)
    assert resposta.status_code == 200
    return {a["id"] for a in resposta.json()["results"]}


def test_a_vitrine_nao_lista_o_anuncio_de_vendedor_desativado(cena: SimpleNamespace) -> None:
    da_ana = anunciar(cena.ana, cena.a1, 1000)
    da_carla = anunciar(cena.carla, cena.c1, 2000)
    bruno = logado(cena.bruno)
    assert _ids_da_vitrine(bruno) == {str(da_ana.pk), str(da_carla.pk)}
    _desativar(cena.ana)

    resposta = bruno.get(LISTINGS_URL)

    assert {a["id"] for a in resposta.json()["results"]} == {str(da_carla.pk)}
    assert resposta.json()["count"] == 1


def test_o_detalhe_do_anuncio_de_vendedor_desativado_da_404_igual_ao_de_inexistente(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    _desativar(cena.ana)
    bruno = logado(cena.bruno)

    escondido = bruno.get(f"{LISTINGS_URL}{anuncio.pk}/")
    inexistente = bruno.get(f"{LISTINGS_URL}{uuid.uuid4()}/")

    assert escondido.status_code == 404
    assert escondido.json() == inexistente.json()


def _resposta_de_anuncio_fechado(cena: SimpleNamespace, comprador: Any) -> Any:
    """A resposta de comprar um anúncio JÁ FECHADO de um vendedor ATIVO (carla cancela o dela).

    É o termo de comparação do vendedor desativado: quem raspou a vitrine guarda o `id` de um
    anúncio e, depois que ele some, só pode pedir a compra desse `id`. Se a resposta do
    desativado diferisse da do fechado, o `id` visto denunciaria a conta desativada.
    """
    delas = anunciar(cena.carla, cena.c1, 500)
    services.cancel_listing(cena.carla, delas.pk, idempotency_key=nova_chave())
    return _comprar(logado(comprador), delas.pk)


def test_comprar_de_vendedor_desativado_da_o_mesmo_409_de_anuncio_fechado_e_nada_se_move(
    cena: SimpleNamespace,
) -> None:
    fechado = _resposta_de_anuncio_fechado(cena, cena.bruno)
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    _desativar(cena.ana)

    desativado = _comprar(logado(cena.bruno), anuncio.pk)

    assert fechado.status_code == 409
    assert fechado.json()["code"] == services.ListingNotActive.code
    assert (desativado.status_code, desativado.json()) == (409, fechado.json())
    _nada_mudou(cena, anuncio)


@pytest.mark.parametrize("fechamento", ["vendido", "cancelado"])
def test_anuncio_ja_fechado_de_vendedor_desativado_da_o_mesmo_409_de_fechado_de_vendedor_ativo(
    cena: SimpleNamespace, fechamento: str
) -> None:
    fechado_de_ativo = _resposta_de_anuncio_fechado(cena, cena.bruno)
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    if fechamento == "vendido":
        assert _comprar(logado(cena.bruno), anuncio.pk).status_code == 201
    else:
        services.cancel_listing(cena.ana, anuncio.pk, idempotency_key=nova_chave())
    _desativar(cena.ana)

    desativado = _comprar(logado(cena.carla), anuncio.pk)

    assert (desativado.status_code, desativado.json()) == (409, fechado_de_ativo.json())


def test_id_inexistente_continua_dando_404_e_so_ele(cena: SimpleNamespace) -> None:
    resposta = _comprar(logado(cena.bruno), uuid.uuid4())

    assert resposta.status_code == 404
    assert resposta.json()["code"] == services.ListingNotFound.code


def test_comprador_e_vendedor_desativados_dao_o_409_do_anuncio_nao_o_do_comprador(
    cena: SimpleNamespace,
) -> None:
    """A checagem do vendedor vem antes da do comprador: a resposta não depende de quem pede."""
    fechado = _resposta_de_anuncio_fechado(cena, cena.bruno)
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    _desativar(cena.ana)
    _desativar(cena.bruno)

    resposta = _comprar(logado(cena.bruno), anuncio.pk)

    assert (resposta.status_code, resposta.json()) == (409, fechado.json())


def test_vendedor_desativado_e_bloqueado_pelo_comprador_da_o_404_do_bloqueio(
    cena: SimpleNamespace,
) -> None:
    """O bloqueio vem primeiro: quem o comprador bloqueou some, desativado ou não."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    friends.block(cena.bruno, cena.ana.username)
    _desativar(cena.ana)
    bruno = logado(cena.bruno)

    escondido = _comprar(bruno, anuncio.pk)
    inexistente = _comprar(bruno, uuid.uuid4())

    assert escondido.status_code == 404
    assert escondido.json() == inexistente.json()


def test_reativado_o_anuncio_volta_a_vitrine(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    bruno = logado(cena.bruno)
    _desativar(cena.ana)
    assert _ids_da_vitrine(bruno) == set()

    _reativar(cena.ana)

    assert _ids_da_vitrine(bruno) == {str(anuncio.pk)}
    assert bruno.get(f"{LISTINGS_URL}{anuncio.pk}/").status_code == 200


def test_comprador_desativado_tambem_e_recusado_no_servico(cena: SimpleNamespace) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    _desativar(cena.bruno)

    with pytest.raises(services.PlayerUnavailable):
        services.buy_listing(cena.bruno, anuncio.pk, idempotency_key=nova_chave())

    _nada_mudou(cena, anuncio)


def test_a_recusa_nao_queima_a_chave_e_reativado_a_mesma_chave_compra(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    chave = nova_chave()
    _desativar(cena.ana)
    assert _comprar(logado(cena.bruno), anuncio.pk, chave).status_code == 409
    _reativar(cena.ana)

    resposta = _comprar(logado(cena.bruno), anuncio.pk, chave)

    assert resposta.status_code == 201, resposta.content
    assert SkinInstance.objects.get(pk=anuncio.instance_id).owner_id == cena.bruno.pk
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000


def test_repetir_uma_compra_ja_feita_devolve_o_recibo_mesmo_com_o_vendedor_desativado_depois(
    cena: SimpleNamespace,
) -> None:
    """A compra já aconteceu: o replay devolve o recibo gravado, sem rodar a regra de novo."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    chave = nova_chave()
    primeira = _comprar(logado(cena.bruno), anuncio.pk, chave)
    assert primeira.status_code == 201
    _desativar(cena.ana)

    segunda = _comprar(logado(cena.bruno), anuncio.pk, chave)

    assert segunda.status_code == 201
    assert segunda.json() == primeira.json()
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000  # debitou uma vez só
