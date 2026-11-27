"""Trocas com um jogador desativado (`is_active=False`): recusa 409 `player_unavailable` (J4).

Decisões do dono (2026-11-27): resposta genérica (um `code` só, sem dizer o motivo), a regra vale
só ao AGIR (criar e aceitar); recusar e cancelar seguem liberados, porque soltam os itens.
O jogador é desativado direto no banco (`.update`), de propósito: os objetos `User` em memória
seguem com `is_active=True`, então só uma leitura do banco, sob a trava dos jogadores, passa.
Cena (conftest): ana e bruno são amigos; carla não é amiga de ninguém.
"""

import uuid
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.inventory.models import SkinInstance
from apps.trades import services
from apps.trades.models import TradeOffer

TRADES_URL = "/api/v1/trades/"
CODE = "player_unavailable"
User: Any = get_user_model()

pytestmark = pytest.mark.django_db


def _desativar(usuario: Any) -> None:
    User.objects.filter(pk=usuario.pk).update(is_active=False)


def _logado(usuario: Any) -> APIClient:
    # `force_authenticate` pula a checagem de sessão: é o que deixa um inativo chegar na view,
    # como um chamador interno chegaria no serviço. Em produção a sessão dele já teria caído.
    client = APIClient()
    client.force_authenticate(usuario)
    return client


def _post(cliente: APIClient, url: str, corpo: Any) -> Any:
    return cliente.post(url, corpo, format="json", headers={"Idempotency-Key": str(uuid.uuid4())})


def _corpo(destino: str, oferecidos: Sequence[Any], pedidos: Sequence[Any]) -> dict[str, Any]:
    return {
        "recipient": destino,
        "offered": [str(i.pk) for i in oferecidos],
        "requested": [str(i.pk) for i in pedidos],
    }


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def _a1_por_b1(cena: SimpleNamespace) -> TradeOffer:
    """ana oferece a1 e pede b1 a bruno, pelo serviço, com os dois ainda ativos."""
    return services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])


# --- criar --------------------------------------------------------------------------------------


def test_propor_a_um_amigo_desativado_da_409_e_nao_cria_oferta(cena: SimpleNamespace) -> None:
    _desativar(cena.bruno)

    resposta = _post(_logado(cena.ana), TRADES_URL, _corpo("bruno_02", [cena.a1], [cena.b1]))

    assert resposta.status_code == 409
    assert set(resposta.json()) == {"code", "message"}
    assert resposta.json()["code"] == CODE
    assert TradeOffer.objects.count() == 0
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)


def test_quem_propoe_desativado_tambem_e_recusado_no_servico(cena: SimpleNamespace) -> None:
    _desativar(cena.ana)

    with pytest.raises(services.PlayerUnavailable):
        services.create_offer(cena.ana, cena.bruno, [cena.a1.pk], [cena.b1.pk])

    assert TradeOffer.objects.count() == 0


def test_desativado_que_nao_e_amigo_continua_dando_not_friends(cena: SimpleNamespace) -> None:
    """A amizade vem ANTES: quem não é amigo não descobre quais contas estão desativadas."""
    _desativar(cena.carla)

    resposta = _post(_logado(cena.ana), TRADES_URL, _corpo("carla_03", [cena.a1], [cena.c1]))

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "not_friends"
    assert TradeOffer.objects.count() == 0


def test_reativado_volta_a_receber_proposta(cena: SimpleNamespace) -> None:
    _desativar(cena.bruno)
    User.objects.filter(pk=cena.bruno.pk).update(is_active=True)

    resposta = _post(_logado(cena.ana), TRADES_URL, _corpo("bruno_02", [cena.a1], [cena.b1]))

    assert resposta.status_code == 201


# --- aceitar ------------------------------------------------------------------------------------


def test_aceitar_com_quem_propos_desativado_da_409_e_ninguem_troca(
    cena: SimpleNamespace,
) -> None:
    oferta = _a1_por_b1(cena)
    _desativar(cena.ana)

    resposta = _post(_logado(cena.bruno), f"{TRADES_URL}{oferta.pk}/accept/", {})

    assert resposta.status_code == 409
    assert resposta.json()["code"] == CODE
    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)
    oferta.refresh_from_db()
    assert (oferta.status, oferta.resolved_at) == ("pending", None)


def test_quem_aceita_desativado_tambem_e_recusado_no_servico(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    _desativar(cena.bruno)

    with pytest.raises(services.PlayerUnavailable):
        services.accept_offer(cena.bruno, oferta.pk)

    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.ana.pk, cena.bruno.pk)
    oferta.refresh_from_db()
    assert oferta.status == "pending"


def test_reativado_o_aceite_volta_a_funcionar_e_os_donos_trocam(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    _desativar(cena.ana)
    with pytest.raises(services.PlayerUnavailable):
        services.accept_offer(cena.bruno, oferta.pk)
    User.objects.filter(pk=cena.ana.pk).update(is_active=True)

    services.accept_offer(cena.bruno, oferta.pk)

    assert (_dono(cena.a1), _dono(cena.b1)) == (cena.bruno.pk, cena.ana.pk)


# --- recusar e cancelar seguem liberados ---------------------------------------------------------


def test_recusar_uma_oferta_de_quem_foi_desativado_funciona_e_solta_os_itens(
    cena: SimpleNamespace,
) -> None:
    oferta = _a1_por_b1(cena)
    _desativar(cena.ana)

    resposta = _post(_logado(cena.bruno), f"{TRADES_URL}{oferta.pk}/decline/", {})

    assert resposta.status_code == 200
    oferta.refresh_from_db()
    assert oferta.status == "declined"


def test_cancelar_uma_oferta_para_quem_foi_desativado_funciona(cena: SimpleNamespace) -> None:
    oferta = _a1_por_b1(cena)
    _desativar(cena.bruno)

    resposta = _post(_logado(cena.ana), f"{TRADES_URL}{oferta.pk}/cancel/", {})

    assert resposta.status_code == 200
    oferta.refresh_from_db()
    assert oferta.status == "cancelled"
