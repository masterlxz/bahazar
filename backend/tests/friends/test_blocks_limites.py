"""Limite do POST de bloquear: throttle por escopo (`friend_block`).

Desde o PR #269, bloquear cancela as ofertas pendentes do par e solta os itens, com trava de linha:
é escrita cara, então ganha teto. 30/min por jogador é HIPÓTESE sem fonte, como os do mercado e
das trocas. Só o POST gasta a cota (desbloquear não restaura nada). O throttle roda antes da view,
então bloquear um usuário que não existe (404) já gasta cota: é o que torna estes testes baratos.
"""

from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from .conftest import bloqueio_url, logado

pytestmark = pytest.mark.django_db

LIMITE = 30
FANTASMA = "ninguem_99"


def _bloquear_fantasma(cliente: APIClient) -> int:
    """POST de bloquear um usuário que não existe: 404 barato, mas conta para o throttle."""
    status_code: int = cliente.post(bloqueio_url(FANTASMA)).status_code
    return status_code


def test_o_escopo_de_bloquear_tem_taxa_configurada() -> None:
    configuracao: Any = settings.REST_FRAMEWORK
    taxas: dict[str, str] = configuracao["DEFAULT_THROTTLE_RATES"]

    assert taxas["friend_block"] == f"{LIMITE}/min"  # hipótese sem fonte


def test_bloquear_leva_429_na_31a_tentativa_por_minuto(ana: Any) -> None:
    cliente = logado(ana)

    estados = [_bloquear_fantasma(cliente) for _ in range(LIMITE + 1)]

    assert estados == [404] * LIMITE + [429]


def test_desbloquear_nao_gasta_nem_sofre_o_limite(ana: Any) -> None:
    cliente = logado(ana)
    for _ in range(LIMITE + 1):
        _bloquear_fantasma(cliente)

    resposta = cliente.delete(bloqueio_url(FANTASMA))

    assert resposta.status_code == 404  # chegou na view (usuário inexistente), não foi barrado


def test_o_limite_e_por_usuario(ana: Any, bruno: Any) -> None:
    cliente_ana = logado(ana)
    for _ in range(LIMITE + 1):
        _bloquear_fantasma(cliente_ana)

    assert _bloquear_fantasma(logado(bruno)) == 404
