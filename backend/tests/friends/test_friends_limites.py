"""Limite dos DELETE que encerram um par: desbloquear e remover amizade (throttle por escopo).

Complementa `test_blocks_limites.py` (o POST de bloquear). `remove_friend` dispara o gancho que
cancela as ofertas pendentes do par (escrita com trava); desbloquear é mais barato, mas fecha o
ciclo bloquear/desbloquear. 30/min por jogador em cada um é HIPÓTESE sem fonte, como os vizinhos.
O throttle roda antes da view, então o alvo que não existe (404) já gasta cota: é o que torna estes
testes baratos. Só o DELETE gasta cota: o GET do perfil não.
"""

from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from .conftest import bloqueio_url, logado, perfil_url

pytestmark = pytest.mark.django_db

LIMITE = 30
FANTASMA = "ninguem_99"


def _desbloquear_fantasma(cliente: APIClient) -> int:
    status_code: int = cliente.delete(bloqueio_url(FANTASMA)).status_code
    return status_code


def _remover_fantasma(cliente: APIClient) -> int:
    status_code: int = cliente.delete(perfil_url(FANTASMA)).status_code
    return status_code


def test_os_escopos_dos_dois_delete_tem_taxa_configurada() -> None:
    configuracao: Any = settings.REST_FRAMEWORK
    taxas: dict[str, str] = configuracao["DEFAULT_THROTTLE_RATES"]

    assert taxas["friend_unblock"] == f"{LIMITE}/min"  # hipótese sem fonte
    assert taxas["friend_remove"] == f"{LIMITE}/min"  # hipótese sem fonte


def test_desbloquear_leva_429_na_31a_tentativa_por_minuto(ana: Any) -> None:
    cliente = logado(ana)

    estados = [_desbloquear_fantasma(cliente) for _ in range(LIMITE + 1)]

    assert estados == [404] * LIMITE + [429]


def test_remover_amizade_leva_429_na_31a_tentativa_por_minuto(ana: Any) -> None:
    cliente = logado(ana)

    estados = [_remover_fantasma(cliente) for _ in range(LIMITE + 1)]

    assert estados == [404] * LIMITE + [429]


def test_ler_o_perfil_nao_gasta_a_cota_de_remover(ana: Any) -> None:
    cliente = logado(ana)
    for _ in range(LIMITE + 1):
        cliente.get(perfil_url(FANTASMA))

    assert _remover_fantasma(cliente) == 404  # chegou na view; 429 seria o GET gastando a cota


def test_os_baldes_de_desbloquear_e_de_remover_sao_independentes(ana: Any) -> None:
    cliente = logado(ana)
    for _ in range(LIMITE + 1):
        _desbloquear_fantasma(cliente)

    assert _remover_fantasma(cliente) == 404
    assert cliente.post(bloqueio_url(FANTASMA)).status_code == 404  # nem o de bloquear


def test_o_limite_e_por_usuario(ana: Any, bruno: Any) -> None:
    cliente_ana = logado(ana)
    for _ in range(LIMITE + 1):
        _remover_fantasma(cliente_ana)

    assert _remover_fantasma(logado(bruno)) == 404
