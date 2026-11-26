"""A compra contra PostgreSQL real: corrida de compradores e ordem de trava (ADR 0016).

Posse e dinheiro são área de risco (AGENTS §4). O que importa é o INVARIANTE depois da corrida
(um comprador, uma venda, ledger fechado), e que a compra espere as travas na ordem do ADR 0016
em vez de formar um ciclo com `trades` e com a criação de anúncio (deadlock, 500 para o jogador).
As esperas são provadas pela fila de `pg_locks` (`_disputar`), não por sorte de temporização.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from apps.economy.audit import check_ledger
from apps.economy.models import Wallet
from apps.inventory.models import SkinInstance
from apps.marketplace import services
from apps.marketplace.models import ListingStatus, MarketListing, MarketTransaction

from ..trades.test_trades_concurrency import _disputar, _travar_instancia, _travar_usuarios
from .conftest import anunciar, criar_usuario
from .test_marketplace_concurrency import _largar
from .test_marketplace_locks import _tentar

pytestmark = pytest.mark.django_db(transaction=True)

SALDO_INICIAL = 2_500


def _comprar(comprador: Any, anuncio: Any) -> Any:
    return services.buy_listing(comprador, anuncio.pk, idempotency_key=str(uuid.uuid4()))


def _tarefa_de_compra(comprador: Any, anuncio: Any) -> Callable[[], Any]:
    """Uma compra pronta para a thread, com uma chave nova a cada execução."""
    return lambda: _comprar(comprador, anuncio)


def _saldo(usuario: Any) -> int:
    return Wallet.objects.get(user=usuario).balance


def test_oito_compradores_ao_mesmo_tempo_so_um_leva_e_o_ledger_fecha(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    compradores = [criar_usuario(f"comprador_{i}") for i in range(8)]

    resultados = _largar([_tarefa_de_compra(c, anuncio) for c in compradores])

    vencedores = [r for r in resultados if isinstance(r, services.PurchaseResult)]
    perdedores = [r for r in resultados if isinstance(r, services.ListingNotActive)]
    assert len(vencedores) == 1
    assert len(perdedores) == 7
    venda = MarketTransaction.objects.get()
    assert venda.pk == vencedores[0].id
    cena.a1.refresh_from_db()
    assert cena.a1.owner_id == venda.buyer_id
    assert [_saldo(c) for c in compradores].count(SALDO_INICIAL - 1000) == 1
    assert [_saldo(c) for c in compradores].count(SALDO_INICIAL) == 7
    assert _saldo(cena.ana) == SALDO_INICIAL + 950
    anuncio.refresh_from_db()
    assert anuncio.status == ListingStatus.SOLD
    assert check_ledger() == []


def test_o_mesmo_comprador_com_chaves_diferentes_ao_mesmo_tempo_paga_uma_vez(
    cena: SimpleNamespace,
) -> None:
    """Duas abas, duas chaves: a idempotência não ajuda, a trava do anúncio é quem decide."""
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    resultados = _largar([_tarefa_de_compra(cena.bruno, anuncio) for _ in range(4)])

    assert sum(isinstance(r, services.PurchaseResult) for r in resultados) == 1
    assert sum(isinstance(r, services.ListingNotActive) for r in resultados) == 3
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000
    assert MarketTransaction.objects.count() == 1
    assert check_ledger() == []


def test_a_mesma_chave_ao_mesmo_tempo_compra_uma_vez_e_devolve_a_mesma_venda(
    cena: SimpleNamespace,
) -> None:
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    chave = str(uuid.uuid4())

    resultados = _largar(
        [(lambda: services.buy_listing(cena.bruno, anuncio.pk, idempotency_key=chave))] * 4
    )

    vendas = {r.id for r in resultados if isinstance(r, services.PurchaseResult)}
    assert len(vendas) == 1
    assert len([r for r in resultados if isinstance(r, services.PurchaseResult)]) == 4
    assert _saldo(cena.bruno) == SALDO_INICIAL - 1000
    assert MarketTransaction.objects.count() == 1
    assert check_ledger() == []


# --- a compra espera as travas na ordem do ADR 0016 --------------------------------------------


@pytest.mark.parametrize(
    "vizinha",
    [("ana",), ("bruno",), ("ana", "bruno")],
    ids=["segura o vendedor", "segura o comprador", "segura os dois"],
)
def test_a_compra_espera_os_jogadores_antes_da_instancia_e_nao_trava_em_ciclo(
    cena: SimpleNamespace, vizinha: tuple[str, ...]
) -> None:
    """A vizinha faz o que `trades` faz: segura os jogadores e SÓ DEPOIS pede a instância.

    Se a compra travasse a instância ANTES dos jogadores, ela seguraria a1 esperando o jogador, a
    vizinha pediria a1 e o PostgreSQL abortaria uma das duas (`deadlock detected`).
    """
    anuncio = anunciar(cena.ana, cena.a1, 1000)
    jogadores = [getattr(cena, nome) for nome in vizinha]

    esperou, resultado = _disputar(
        trava=lambda: _travar_usuarios(*jogadores),
        depois=lambda: _travar_instancia(cena.a1),
        operacao=_tentar(lambda: _comprar(cena.bruno, anuncio)),
    )

    assert esperou, "a compra não esperou os jogadores"
    assert isinstance(resultado, services.PurchaseResult)
    assert MarketTransaction.objects.count() == 1
    assert check_ledger() == []


def test_a_compra_confere_o_anuncio_sob_a_trava_dele(cena: SimpleNamespace) -> None:
    """A vizinha segura o anúncio e o cancela; a compra esperava e tem de recusar com 409.

    Mutação que derruba este teste: tirar o `select_for_update()` do anúncio em `buy_listing`.
    Ela leria o anúncio ainda ativo e venderia um anúncio que o vendedor acabou de cancelar.
    """
    anuncio = anunciar(cena.ana, cena.a1, 1000)

    def cancelar_por_fora() -> None:
        MarketListing.objects.filter(pk=anuncio.pk).update(
            status=ListingStatus.CANCELLED, closed_at=datetime.now(UTC)
        )

    esperou, resultado = _disputar(
        trava=lambda: list(MarketListing.objects.select_for_update().filter(pk=anuncio.pk)),
        depois=cancelar_por_fora,
        operacao=_tentar(lambda: _comprar(cena.bruno, anuncio)),
    )

    assert esperou, "a compra não esperou a trava do anúncio"
    assert type(resultado) is services.ListingNotActive
    assert MarketTransaction.objects.count() == 0
    assert _saldo(cena.bruno) == SALDO_INICIAL
    assert check_ledger() == []


@pytest.mark.parametrize("mudanca", ["dono", "consumo"])
def test_a_compra_confere_dono_e_consumo_sob_a_trava_da_instancia(
    cena: SimpleNamespace, mudanca: str
) -> None:
    """A vizinha segura a1 e, antes de comitar, muda o dono ou consome o item.

    Mutação que derruba este teste: tirar o `select_for_update()` da instância em `buy_listing`.
    A compra leria o dono antigo e moveria dinheiro por um item que já mudou de mãos.
    """

    def trocar_dono() -> None:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(owner=cena.carla)

    def consumir() -> None:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(consumed_at=datetime.now(UTC))

    anuncio = anunciar(cena.ana, cena.a1, 1000)

    esperou, resultado = _disputar(
        trava=lambda: _travar_instancia(cena.a1),
        depois=trocar_dono if mudanca == "dono" else consumir,
        operacao=_tentar(lambda: _comprar(cena.bruno, anuncio)),
    )

    assert esperou, "a compra não esperou a trava da instância"
    assert type(resultado) is services.ListingUnavailable
    assert MarketTransaction.objects.count() == 0
    assert _saldo(cena.bruno) == SALDO_INICIAL
    assert _saldo(cena.ana) == SALDO_INICIAL
    assert check_ledger() == []
