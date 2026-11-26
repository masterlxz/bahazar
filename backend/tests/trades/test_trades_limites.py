"""Limites das trocas: throttle por escopo nos 4 POST (A2 a, Sessão 43).

Decisão do dono (2026-11-26): criar 30/min e aceitar, recusar e cancelar 60/min por jogador, os
dois HIPÓTESES sem fonte, como os do mercado. Criar tem escopo próprio (`trade_create`); as três
resoluções dividem UM balde (`trade_resolve`). O throttle roda antes da view, então um corpo
inválido (400) ou um 404 já gasta cota: é o que torna estes testes baratos.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

TRADES_URL = "/api/v1/trades/"
UM_ID_QUALQUER = "7c0f8e1a-0000-4000-8000-000000000001"
CRIAR = 30
RESOLVER = 60
ACOES = ("accept", "decline", "cancel")

pytestmark = pytest.mark.django_db


def _logado(usuario: Any) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


def _criar_vazio(cliente: APIClient) -> int:
    """POST de criar com corpo vazio: 400 barato, mas conta para o throttle (ele roda antes)."""
    status_code: int = cliente.post(TRADES_URL, {}, format="json").status_code
    return status_code


def _resolver(cliente: APIClient, acao: str) -> int:
    """POST de resolver uma oferta que não existe: 404 barato (a chave é nova a cada pedido)."""
    url = f"{TRADES_URL}{UM_ID_QUALQUER}/{acao}/"
    resposta = cliente.post(url, {}, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    status_code: int = resposta.status_code
    return status_code


def test_os_escopos_das_trocas_tem_taxa_configurada() -> None:
    configuracao: Any = settings.REST_FRAMEWORK
    taxas: dict[str, str] = configuracao["DEFAULT_THROTTLE_RATES"]

    assert taxas["trade_create"] == f"{CRIAR}/min"  # hipótese sem fonte
    assert taxas["trade_resolve"] == f"{RESOLVER}/min"  # hipótese sem fonte


def test_criar_oferta_leva_429_na_31a_tentativa_por_minuto(cena: SimpleNamespace) -> None:
    ana = _logado(cena.ana)

    estados = [_criar_vazio(ana) for _ in range(CRIAR + 1)]

    assert estados == [400] * CRIAR + [429]


@pytest.mark.parametrize("acao", ACOES)
def test_resolver_leva_429_na_61a_tentativa_por_minuto(cena: SimpleNamespace, acao: str) -> None:
    ana = _logado(cena.ana)

    estados = [_resolver(ana, acao) for _ in range(RESOLVER + 1)]

    assert estados == [404] * RESOLVER + [429]


def test_aceitar_recusar_e_cancelar_dividem_o_mesmo_balde(cena: SimpleNamespace) -> None:
    """20 de cada rota esgotam a cota de 60; a 61ª leva 429 em QUALQUER das três."""
    ana = _logado(cena.ana)
    por_rota = RESOLVER // len(ACOES)

    estados = [_resolver(ana, acao) for acao in ACOES for _ in range(por_rota)]

    assert estados == [404] * RESOLVER
    assert [_resolver(ana, acao) for acao in ACOES] == [429, 429, 429]


def test_os_baldes_de_criar_e_de_resolver_sao_independentes(cena: SimpleNamespace) -> None:
    ana = _logado(cena.ana)
    for _ in range(CRIAR):
        _criar_vazio(ana)
    assert _criar_vazio(ana) == 429

    assert _resolver(ana, "cancel") == 404  # resolver continua livre

    for _ in range(RESOLVER - 1):  # o `cancel` acima já gastou uma
        _resolver(ana, "accept")
    assert _resolver(ana, "accept") == 429
    assert _criar_vazio(ana) == 429  # e o de criar segue esgotado: nenhum devolveu cota ao outro


def test_ler_a_lista_nao_gasta_a_cota_de_criar(cena: SimpleNamespace) -> None:
    """Sem `get_throttles` por método, 30 GETs esgotariam o balde do POST e criar levaria 429."""
    ana = _logado(cena.ana)

    leituras = [ana.get(TRADES_URL).status_code for _ in range(CRIAR)]

    assert leituras == [200] * CRIAR
    assert _criar_vazio(ana) == 400


def test_o_limite_e_por_usuario(cena: SimpleNamespace) -> None:
    ana, bruno = _logado(cena.ana), _logado(cena.bruno)
    for _ in range(CRIAR):
        _criar_vazio(ana)
    for _ in range(RESOLVER):
        _resolver(ana, "accept")

    assert _criar_vazio(ana) == 429
    assert _resolver(ana, "accept") == 429
    assert _criar_vazio(bruno) == 400
    assert _resolver(bruno, "accept") == 404
