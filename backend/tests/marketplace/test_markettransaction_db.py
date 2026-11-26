"""`market_transactions` no banco: constraints, venda única por anúncio e imutabilidade (trigger).

Dinheiro e posse são área de risco (AGENTS §4): o banco é a última defesa, então cada regra é
provada com um `INSERT` ou `UPDATE` direto, sem passar pelo serviço.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import ProtectedError

from apps.marketplace.models import ListingStatus, MarketListing, MarketTransaction

pytestmark = pytest.mark.django_db

_FECHADO_EM = datetime(2026, 1, 1, tzinfo=UTC)


def _anuncio_vendido(cena: SimpleNamespace, instancia: Any = None, price: int = 1000) -> Any:
    """Um anúncio já fechado como vendido, gravado direto (a compra de verdade vem no serviço)."""
    return MarketListing.objects.create(
        seller=cena.ana,
        instance=instancia or cena.a1,
        price=price,
        status=ListingStatus.SOLD,
        closed_at=_FECHADO_EM,
    )


def _venda(cena: SimpleNamespace, anuncio: Any, **mudancas: Any) -> Any:
    dados: dict[str, Any] = {
        "listing": anuncio,
        "buyer": cena.bruno,
        "seller": cena.ana,
        "price": 1000,
        "fee": 50,
        "ledger_group_id": uuid.uuid4(),
    }
    dados.update(mudancas)
    return MarketTransaction.objects.create(**dados)


def test_uma_venda_valida_grava(cena: SimpleNamespace) -> None:
    venda = _venda(cena, _anuncio_vendido(cena))

    assert MarketTransaction.objects.get(pk=venda.pk).fee == 50


def test_um_anuncio_so_vende_uma_vez(cena: SimpleNamespace) -> None:
    anuncio = _anuncio_vendido(cena)
    _venda(cena, anuncio)

    with pytest.raises(IntegrityError), transaction.atomic():
        _venda(cena, anuncio, buyer=cena.carla)


def test_comprador_e_vendedor_nao_podem_ser_a_mesma_pessoa(cena: SimpleNamespace) -> None:
    with pytest.raises(IntegrityError, match="markettx_buyer_not_seller"), transaction.atomic():
        _venda(cena, _anuncio_vendido(cena), buyer=cena.ana)


@pytest.mark.parametrize(
    ("preco", "taxa"), [(1000, -1), (1000, 1000), (1000, 1001), (0, 0), (-5, 0)]
)
def test_taxa_fica_de_zero_ate_antes_do_preco(cena: SimpleNamespace, preco: int, taxa: int) -> None:
    """O vendedor nunca recebe zero ou menos: `0 <= taxa < preco` (isso também exige preço > 0)."""
    with pytest.raises(IntegrityError, match="markettx_fee_below_price"), transaction.atomic():
        _venda(cena, _anuncio_vendido(cena), price=preco, fee=taxa)


def test_a_taxa_zero_vale(cena: SimpleNamespace) -> None:
    venda = _venda(cena, _anuncio_vendido(cena, price=19), price=19, fee=0)

    assert venda.fee == 0


def test_o_trigger_barra_update_e_delete_ate_por_sql_direto(cena: SimpleNamespace) -> None:
    venda = _venda(cena, _anuncio_vendido(cena))

    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE marketplace_markettransaction SET fee = 0 WHERE id = %s", [venda.pk]
            )
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM marketplace_markettransaction WHERE id = %s", [venda.pk])

    assert MarketTransaction.objects.get(pk=venda.pk).fee == 50


def test_nao_se_apaga_o_anuncio_que_ja_tem_venda(cena: SimpleNamespace) -> None:
    """A FK `listing` é PROTECT. O `match` aponta a FK da venda: o anúncio não tem outro vínculo
    que o bloquearia sozinho. (`buyer` e `seller` também são PROTECT, mas um jogador com venda
    sempre tem item, carteira e anúncio que o protegem antes: não dá para provar a FK isolada.)"""
    anuncio = _anuncio_vendido(cena)
    _venda(cena, anuncio)

    with pytest.raises(ProtectedError, match=r"MarketTransaction\.listing"), transaction.atomic():
        anuncio.delete()

    assert MarketTransaction.objects.count() == 1
