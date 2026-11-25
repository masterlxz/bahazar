"""API da carteira: só a própria, só leitura, e a diária nunca aceita valor vindo do cliente."""

from datetime import timedelta
from typing import Any

import pytest
from pytest import MonkeyPatch
from rest_framework.test import APIClient

from apps.economy import services
from apps.economy.models import Wallet

from .conftest import DAILY_URL, T0, WALLET_URL, criar_usuario, logado

pytestmark = pytest.mark.django_db


def _relogio(monkeypatch: MonkeyPatch, agora: Any) -> None:
    monkeypatch.setattr(services, "_now", lambda: agora)


def test_anonimo_nao_ve_carteira_nem_resgata() -> None:
    assert APIClient().get(WALLET_URL).status_code in (401, 403)
    assert APIClient().post(DAILY_URL, {}, format="json").status_code in (401, 403)


def test_jogador_ve_o_proprio_saldo_e_a_diaria_disponivel(
    ana: Any, monkeypatch: MonkeyPatch
) -> None:
    _relogio(monkeypatch, T0)

    resposta = logado(ana).get(WALLET_URL)

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["balance"] == 2_500
    assert dados["daily"] == {
        "can_claim": True,
        "available_at": None,
        "next_streak_day": 1,
        "next_amount": 250,
    }


def test_cada_jogador_ve_so_a_propria_carteira(ana: Any, monkeypatch: MonkeyPatch) -> None:
    bruno = criar_usuario("bruno_02")
    _relogio(monkeypatch, T0)
    logado(ana).post(DAILY_URL, {}, format="json")

    assert logado(ana).get(WALLET_URL).json()["balance"] == 2_750
    assert logado(bruno).get(WALLET_URL).json()["balance"] == 2_500


@pytest.mark.parametrize("metodo", ["put", "patch", "delete", "post"])
def test_carteira_nao_tem_endpoint_de_escrita(ana: Any, metodo: str) -> None:
    resposta = getattr(logado(ana), metodo)(WALLET_URL, {"balance": 10**9}, format="json")

    assert resposta.status_code == 405
    assert Wallet.objects.get(user=ana).balance == 2_500


def test_resgate_ignora_valor_vindo_do_cliente(ana: Any, monkeypatch: MonkeyPatch) -> None:
    _relogio(monkeypatch, T0)

    resposta = logado(ana).post(
        DAILY_URL, {"amount": 999_999, "streak_day": 30, "balance": 10**9}, format="json"
    )

    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["amount"] == 250
    assert dados["streak_day"] == 1
    assert dados["balance"] == 2_750


def test_segundo_resgate_antes_de_24h_da_409_com_quando_libera(
    ana: Any, monkeypatch: MonkeyPatch
) -> None:
    _relogio(monkeypatch, T0)
    logado(ana).post(DAILY_URL, {}, format="json")
    _relogio(monkeypatch, T0 + timedelta(hours=23))

    resposta = logado(ana).post(DAILY_URL, {}, format="json")

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["code"] == "daily_not_ready"
    assert corpo["available_at"].startswith("2026-11-21T12:00:00")
    assert Wallet.objects.get(user=ana).balance == 2_750


def test_resgate_no_dia_seguinte_paga_mais(ana: Any, monkeypatch: MonkeyPatch) -> None:
    _relogio(monkeypatch, T0)
    logado(ana).post(DAILY_URL, {}, format="json")
    _relogio(monkeypatch, T0 + timedelta(hours=24))

    resposta = logado(ana).post(DAILY_URL, {}, format="json")

    assert resposta.status_code == 201
    assert resposta.json()["amount"] == 500
    assert resposta.json()["balance"] == 3_250


def test_usuario_sem_carteira_ganha_uma_ao_consultar(ana: Any, monkeypatch: MonkeyPatch) -> None:
    """Auto-cura: se a criação da carteira falhou no cadastro, a primeira consulta a cria."""

    def falha(usuario: Any) -> None:
        raise RuntimeError("falha simulada ao abrir a carteira")

    with monkeypatch.context() as m:
        m.setattr(services, "open_wallet", falha)
        with pytest.raises(RuntimeError):
            criar_usuario("sem_carteira")

    sem = type(ana).objects.get(username="sem_carteira")
    assert not Wallet.objects.filter(user=sem).exists()

    resposta = logado(sem).get(WALLET_URL)

    assert resposta.status_code == 200
    assert resposta.json()["balance"] == 2_500
