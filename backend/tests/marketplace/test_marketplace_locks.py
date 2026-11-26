"""Ordem e efeito das travas do mercado contra PostgreSQL real, de forma determinística.

Posse de item é área de risco (AGENTS §4). Cada teste usa uma transação "vizinha" que segura uma
trava (`_disputar`, o mesmo mecanismo de `tests/trades/test_trades_concurrency.py`) e PROVA, pela
fila em `pg_locks`, que a operação esperou. Uma corrida pura (`test_marketplace_concurrency.py`)
passa mesmo sem a trava, porque o índice único parcial barra o segundo anúncio; estes não.

Os erros de mercado voltam como VALOR (`_tentar`): `_Disparo` só devolve `TradeError` como valor.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from apps.accounts.models import User
from apps.inventory.models import SkinInstance
from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketListing

from ..trades.test_trades_concurrency import _disputar, _travar_instancia
from .conftest import anunciar, nova_chave

pytestmark = pytest.mark.django_db(transaction=True)


def _tentar(operacao: Callable[[], Any]) -> Callable[[], Any]:
    """Devolve o erro de mercado como valor, para o teste inspecionar o tipo."""

    def rodar() -> Any:
        try:
            return operacao()
        except services.MarketError as erro:
            return erro

    return rodar


def _travar_vendedor(vendedor: Any) -> None:
    """`FOR UPDATE` pleno no jogador, como `trades._travar_jogadores`.

    Pleno de propósito: é o que conflita com o `KEY SHARE` que a FK do anúncio toma no vendedor.
    """
    list(User.objects.select_for_update().filter(pk=vendedor.pk))


def test_criar_anuncio_trava_o_vendedor_antes_da_instancia(cena: SimpleNamespace) -> None:
    """A vizinha faz o que `trades` faz: segura o vendedor e SÓ DEPOIS pede a instância.

    O anúncio tem FK para o vendedor (`KEY SHARE` na linha dele, que conflita com o `FOR UPDATE`
    da vizinha). Se `create_listing` travar a instância ANTES do vendedor, ele segura a1 esperando
    o vendedor, a vizinha pede a1 e dá deadlock (o Postgres aborta uma das duas depois de 1 s:
    erro 500 para o jogador). Travando o vendedor primeiro, ele espera sem segurar nada, a
    vizinha termina, e o anúncio sai. Mutação que derruba este teste: tirar a trava do vendedor.
    """
    esperou, resultado = _disputar(
        trava=lambda: _travar_vendedor(cena.ana),
        depois=lambda: _travar_instancia(cena.a1),
        operacao=_tentar(
            lambda: services.create_listing(cena.ana, cena.a1.pk, 500, idempotency_key=nova_chave())
        ),
    )

    assert esperou, "o anúncio não esperou a trava do vendedor"
    assert isinstance(resultado, services.ListingOutcome)
    assert MarketListing.objects.filter(instance=cena.a1, status=ListingStatus.ACTIVE).count() == 1


@pytest.mark.parametrize("mudanca", ["dono", "consumo"])
def test_criar_anuncio_confere_dono_e_consumo_sob_a_trava_da_instancia(
    cena: SimpleNamespace, mudanca: str
) -> None:
    """A vizinha segura a1 e, antes de comitar, muda o dono ou consome o item; o anúncio esperava.

    O anúncio tem de ler dono e consumo DEPOIS de obter a trava da instância e recusar. Mutação
    que derruba este teste: tirar o `select_for_update()` da leitura da instância em
    `create_listing`. Ele leria a1 sem esperar, veria o dono antigo e não consumido, e gravaria o
    anúncio de um item que já saiu do jogo ou mudou de mãos. (O índice único não ajuda aqui: a
    outra transação não cria anúncio.)
    """

    def trocar_dono() -> None:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(owner=cena.carla)

    def consumir() -> None:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(consumed_at=datetime.now(UTC))

    esperou, resultado = _disputar(
        trava=lambda: _travar_instancia(cena.a1),
        depois=trocar_dono if mudanca == "dono" else consumir,
        operacao=_tentar(
            lambda: services.create_listing(cena.ana, cena.a1.pk, 500, idempotency_key=nova_chave())
        ),
    )

    esperado = services.InstanceNotFound if mudanca == "dono" else services.ItemConsumed
    assert esperou, "o anúncio não esperou a trava da instância"
    assert type(resultado) is esperado
    assert MarketListing.objects.count() == 0


def test_cancelar_confere_o_estado_sob_a_trava_do_anuncio(cena: SimpleNamespace) -> None:
    """A vizinha segura o anúncio e o cancela; o cancelamento que esperava recusa com 409.

    Mutação que derruba este teste: tirar o `select_for_update()` de `cancel_listing`. Ele leria
    o anúncio ainda ativo, e só o `UPDATE` esperaria a vizinha: ao acordar, "cancelaria" um
    anúncio já cancelado e devolveria sucesso, com `closed_at` regravado por cima.
    """
    anuncio = anunciar(cena.ana, cena.a1)
    fechamento = datetime(2026, 1, 1, tzinfo=UTC)

    def cancelar_por_fora() -> None:
        MarketListing.objects.filter(pk=anuncio.pk).update(
            status=ListingStatus.CANCELLED, closed_at=fechamento
        )

    def travar_anuncio() -> None:
        list(MarketListing.objects.select_for_update(no_key=True).filter(pk=anuncio.pk))

    esperou, resultado = _disputar(
        trava=travar_anuncio,
        depois=cancelar_por_fora,
        operacao=_tentar(
            lambda: services.cancel_listing(cena.ana, anuncio.pk, idempotency_key=nova_chave())
        ),
    )

    assert esperou, "o cancelamento não esperou a trava do anúncio"
    assert isinstance(resultado, services.ListingNotActive)
    gravado = MarketListing.objects.get(pk=anuncio.pk)
    assert gravado.status == ListingStatus.CANCELLED
    assert gravado.closed_at == fechamento
