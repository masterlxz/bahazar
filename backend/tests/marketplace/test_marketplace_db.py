"""Garantias do banco para o mercado: valem mesmo que o serviço tenha bug.

Mesmo padrão de `tests/trades/test_trades_db.py`: cada teste fere UMA constraint, e o `match`
confere o nome dela (a mensagem do PostgreSQL cita a constraint violada). Os testes de serviço e
de API passam pelas regras em Python; estes escrevem direto pelo ORM, que é o caminho de um bug
futuro, do admin ou de um `UPDATE` à mão.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.marketplace.models import ListingStatus, MarketListing

pytestmark = pytest.mark.django_db


def _anuncio(cena: SimpleNamespace, **extra: Any) -> MarketListing:
    dados: dict[str, Any] = {
        "seller": cena.ana,
        "instance": cena.a1,
        "price": 1000,
        "status": ListingStatus.ACTIVE,
    }
    return MarketListing.objects.create(**{**dados, **extra})


# --- preço e estado ----------------------------------------------------------------------------


@pytest.mark.parametrize("preco", [0, -1])
def test_banco_recusa_preco_que_nao_e_positivo(cena: SimpleNamespace, preco: int) -> None:
    with pytest.raises(IntegrityError, match="marketlisting_price_positive"):
        with transaction.atomic():
            _anuncio(cena, price=preco)

    assert MarketListing.objects.count() == 0


def test_banco_recusa_estado_desconhecido(cena: SimpleNamespace) -> None:
    with pytest.raises(IntegrityError, match="marketlisting_status_valid"):
        with transaction.atomic():
            _anuncio(cena, status="pending", closed_at=timezone.now())

    assert MarketListing.objects.count() == 0


# --- `closed_at` nulo se, e só se, o anúncio está ativo ------------------------------------------


def test_banco_recusa_anuncio_ativo_com_data_de_fechamento(cena: SimpleNamespace) -> None:
    with pytest.raises(IntegrityError, match="marketlisting_closed_matches_status"):
        with transaction.atomic():
            _anuncio(cena, closed_at=timezone.now())

    assert MarketListing.objects.count() == 0


@pytest.mark.parametrize("status", [ListingStatus.SOLD, ListingStatus.CANCELLED])
def test_banco_recusa_anuncio_fechado_sem_data_de_fechamento(
    cena: SimpleNamespace, status: str
) -> None:
    with pytest.raises(IntegrityError, match="marketlisting_closed_matches_status"):
        with transaction.atomic():
            _anuncio(cena, status=status, closed_at=None)

    assert MarketListing.objects.count() == 0


def test_banco_recusa_reabrir_um_anuncio_sem_limpar_o_fechamento(cena: SimpleNamespace) -> None:
    """Um `UPDATE` que volta `cancelled` para `active` e esquece o `closed_at` não passa."""
    anuncio = _anuncio(cena, status=ListingStatus.CANCELLED, closed_at=timezone.now())

    with pytest.raises(IntegrityError, match="marketlisting_closed_matches_status"):
        with transaction.atomic():
            MarketListing.objects.filter(pk=anuncio.pk).update(status=ListingStatus.ACTIVE)

    assert MarketListing.objects.get(pk=anuncio.pk).status == ListingStatus.CANCELLED


@pytest.mark.parametrize("status", [ListingStatus.SOLD, ListingStatus.CANCELLED])
def test_banco_aceita_anuncio_fechado_com_data_de_fechamento(
    cena: SimpleNamespace, status: str
) -> None:
    anuncio = _anuncio(cena, status=status, closed_at=timezone.now())

    assert MarketListing.objects.get(pk=anuncio.pk).status == status


def test_banco_aceita_anuncio_ativo_sem_data_de_fechamento(cena: SimpleNamespace) -> None:
    anuncio = _anuncio(cena)

    assert MarketListing.objects.get(pk=anuncio.pk).closed_at is None


# --- uma instância, no máximo um anúncio ativo ---------------------------------------------------


def test_banco_recusa_dois_anuncios_ativos_da_mesma_instancia(cena: SimpleNamespace) -> None:
    _anuncio(cena)

    with pytest.raises(IntegrityError, match="marketlist_one_active_instance"):
        with transaction.atomic():
            _anuncio(cena, price=2000)

    assert MarketListing.objects.count() == 1


def test_banco_aceita_varios_anuncios_resolvidos_e_um_ativo_da_mesma_instancia(
    cena: SimpleNamespace,
) -> None:
    for status in (ListingStatus.SOLD, ListingStatus.CANCELLED, ListingStatus.CANCELLED):
        _anuncio(cena, status=status, closed_at=timezone.now())

    _anuncio(cena)

    assert MarketListing.objects.filter(instance=cena.a1).count() == 4


# --- o histórico não se apaga --------------------------------------------------------------------


def test_banco_nao_deixa_apagar_o_vendedor_com_anuncio(cena: SimpleNamespace) -> None:
    _anuncio(cena)

    with pytest.raises(ProtectedError):
        cena.ana.delete()

    assert MarketListing.objects.count() == 1


def test_banco_nao_deixa_apagar_a_instancia_com_anuncio(cena: SimpleNamespace) -> None:
    _anuncio(cena)

    with pytest.raises(ProtectedError):
        cena.a1.delete()

    assert MarketListing.objects.count() == 1
