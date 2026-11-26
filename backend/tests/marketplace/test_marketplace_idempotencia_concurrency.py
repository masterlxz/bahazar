"""Criar e cancelar anúncio com a MESMA chave ao mesmo tempo, contra PostgreSQL real (4.4b).

O `INSERT` do registro de idempotência faz a segunda transação esperar a primeira e só então
falhar por unicidade; daí vem a resposta gravada (ADR 0014). O que importa é o invariante: uma
execução só, e todas as respostas iguais.
"""

from types import SimpleNamespace

import pytest

from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketListing

from .conftest import anunciar, nova_chave
from .test_marketplace_concurrency import _largar

pytestmark = pytest.mark.django_db(transaction=True)

SIMULTANEAS = 6


def test_a_mesma_chave_ao_mesmo_tempo_cria_um_anuncio_e_devolve_o_mesmo_corpo(
    cena: SimpleNamespace,
) -> None:
    chave = nova_chave()
    tarefas = [
        lambda: services.create_listing(cena.ana, cena.a1.pk, 500, idempotency_key=chave)
        for _ in range(SIMULTANEAS)
    ]

    resultados = _largar(tarefas)

    assert all(isinstance(r, services.ListingOutcome) for r in resultados), resultados
    assert {r.body["id"] for r in resultados} == {str(MarketListing.objects.get().pk)}
    assert sum(not r.replayed for r in resultados) == 1
    assert MarketListing.objects.count() == 1


def test_a_mesma_chave_ao_mesmo_tempo_cancela_uma_vez_e_todas_devolvem_200(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1)
    chave = nova_chave()
    tarefas = [
        lambda: services.cancel_listing(cena.ana, anuncio.pk, idempotency_key=chave)
        for _ in range(SIMULTANEAS)
    ]

    resultados = _largar(tarefas)

    assert all(isinstance(r, services.ListingOutcome) for r in resultados), resultados
    assert {r.status for r in resultados} == {200}
    assert sum(not r.replayed for r in resultados) == 1
    assert MarketListing.objects.get().status == ListingStatus.CANCELLED
