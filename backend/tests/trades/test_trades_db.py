"""Garantias do banco para as trocas: valem mesmo que o serviço tenha bug.

Mesmo padrão de `tests/inventory/test_instances_db.py`: cada teste fere UMA constraint, e o
`match` confere o nome dela (a mensagem do PostgreSQL cita a constraint violada).
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.trades import services
from apps.trades.models import TradeOffer, TradeOfferItem

pytestmark = pytest.mark.django_db


def _oferta(cena: SimpleNamespace, **extra: Any) -> TradeOffer:
    dados: dict[str, Any] = {"proposer": cena.ana, "recipient": cena.bruno, "status": "pending"}
    return TradeOffer.objects.create(**{**dados, **extra})


def _item(oferta: TradeOffer, instancia: Any, *, ativo: bool, lado: str = "offered") -> Any:
    return TradeOfferItem.objects.create(offer=oferta, instance=instancia, side=lado, active=ativo)


# --- uma instância em no máximo uma oferta pendente --------------------------------------------


def test_banco_recusa_a_mesma_instancia_em_duas_ofertas_ativas(cena: SimpleNamespace) -> None:
    _item(_oferta(cena), cena.a1, ativo=True)
    outra = _oferta(cena, recipient=cena.carla)

    with pytest.raises(IntegrityError, match="tradeitem_one_active_per_instance"):
        with transaction.atomic():
            _item(outra, cena.a1, ativo=True, lado="requested")

    assert TradeOfferItem.objects.filter(instance=cena.a1).count() == 1


def test_o_indice_vale_para_os_dois_lados_da_oferta(cena: SimpleNamespace) -> None:
    """b1 é pedido por ana numa oferta e oferecido por bruno noutra: também recusado."""
    _item(_oferta(cena), cena.b1, ativo=True, lado="requested")
    outra = _oferta(cena, proposer=cena.bruno, recipient=cena.ana)

    with pytest.raises(IntegrityError, match="tradeitem_one_active_per_instance"):
        with transaction.atomic():
            _item(outra, cena.b1, ativo=True, lado="offered")


def test_banco_aceita_a_mesma_instancia_em_varias_ofertas_ja_resolvidas(
    cena: SimpleNamespace,
) -> None:
    for _ in range(3):
        _item(_oferta(cena), cena.a1, ativo=False)

    assert TradeOfferItem.objects.filter(instance=cena.a1, active=False).count() == 3


def test_banco_aceita_uma_ativa_junto_de_varias_resolvidas(cena: SimpleNamespace) -> None:
    _item(_oferta(cena), cena.a1, ativo=False)
    _item(_oferta(cena), cena.a1, ativo=False)

    _item(_oferta(cena), cena.a1, ativo=True)

    assert TradeOfferItem.objects.filter(instance=cena.a1, active=True).count() == 1


def test_desligar_o_item_libera_a_instancia_para_outra_oferta(cena: SimpleNamespace) -> None:
    primeiro = _item(_oferta(cena), cena.a1, ativo=True)
    TradeOfferItem.objects.filter(pk=primeiro.pk).update(active=False)

    _item(_oferta(cena), cena.a1, ativo=True)

    assert TradeOfferItem.objects.filter(instance=cena.a1, active=True).count() == 1


def test_banco_recusa_a_mesma_instancia_duas_vezes_na_mesma_oferta(cena: SimpleNamespace) -> None:
    oferta = _oferta(cena)
    _item(oferta, cena.a1, ativo=False)

    with pytest.raises(IntegrityError, match="tradeitem_unique_offer_instance"):
        with transaction.atomic():
            _item(oferta, cena.a1, ativo=False, lado="requested")


# --- CHECKs da oferta e do item ----------------------------------------------------------------


def test_banco_recusa_auto_oferta(cena: SimpleNamespace) -> None:
    with pytest.raises(IntegrityError, match="tradeoffer_no_self"):
        with transaction.atomic():
            _oferta(cena, recipient=cena.ana)

    assert TradeOffer.objects.count() == 0


def test_banco_recusa_estado_desconhecido(cena: SimpleNamespace) -> None:
    with pytest.raises(IntegrityError, match="tradeoffer_status_valid"):
        with transaction.atomic():
            _oferta(cena, status="expired", resolved_at=datetime.now(UTC))


def test_banco_recusa_lado_desconhecido(cena: SimpleNamespace) -> None:
    oferta = _oferta(cena)

    with pytest.raises(IntegrityError, match="tradeitem_side_valid"):
        with transaction.atomic():
            _item(oferta, cena.a1, ativo=True, lado="dado")


@pytest.mark.parametrize(
    ("status", "resolved_at"),
    [
        ("pending", datetime(2026, 11, 25, 12, 0, tzinfo=UTC)),
        ("accepted", None),
        ("declined", None),
        ("cancelled", None),
    ],
    ids=["pendente com data de fim", "aceita sem data", "recusada sem data", "cancelada sem data"],
)
def test_banco_exige_data_de_fim_so_nas_ofertas_resolvidas(
    cena: SimpleNamespace, status: str, resolved_at: datetime | None
) -> None:
    with pytest.raises(IntegrityError, match="tradeoffer_resolved_matches_status"):
        with transaction.atomic():
            _oferta(cena, status=status, resolved_at=resolved_at)


@pytest.mark.parametrize("status", ["accepted", "declined", "cancelled"])
def test_banco_aceita_oferta_resolvida_com_data_de_fim(cena: SimpleNamespace, status: str) -> None:
    oferta = _oferta(cena, status=status, resolved_at=datetime(2026, 11, 25, 12, 0, tzinfo=UTC))

    assert TradeOffer.objects.get(pk=oferta.pk).status == status


# --- como o serviço reconhece a constraint violada ---------------------------------------------


class _CausaComDiag(Exception):
    """Imita a causa do driver: uma exceção com `diag.constraint_name`."""

    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("causa")
        self.diag = SimpleNamespace(constraint_name=constraint_name)


def test_o_nome_da_constraint_vem_do_diag_do_driver_numa_violacao_real(
    cena: SimpleNamespace,
) -> None:
    _item(_oferta(cena), cena.a1, ativo=True)
    outra = _oferta(cena, recipient=cena.carla)

    with pytest.raises(IntegrityError) as capturado, transaction.atomic():
        _item(outra, cena.a1, ativo=True, lado="requested")

    assert services.violated_constraint(capturado.value) == "tradeitem_one_active_per_instance"


def test_o_diag_vence_o_texto_da_mensagem() -> None:
    erro = IntegrityError('violates unique constraint "so_no_texto"')
    erro.__cause__ = _CausaComDiag("no_diag")

    assert services.violated_constraint(erro) == "no_diag"


@pytest.mark.parametrize(
    "causa",
    [None, ValueError("sem diag"), _CausaComDiag(None)],
    ids=["sem causa", "causa sem diag", "diag sem nome"],
)
def test_sem_diag_usa_o_nome_que_a_mensagem_cita(causa: BaseException | None) -> None:
    erro = IntegrityError('duplicate key value violates unique constraint "so_no_texto"')
    erro.__cause__ = causa

    assert services.violated_constraint(erro) == "so_no_texto"


def test_sem_diag_e_sem_nome_na_mensagem_nao_ha_constraint_a_reconhecer() -> None:
    assert services.violated_constraint(IntegrityError("falha qualquer")) is None


def test_um_nome_parecido_dentro_do_texto_nao_conta_como_a_constraint() -> None:
    """O texto só vale quando cita uma constraint entre aspas; o nome solto não casa."""
    erro = IntegrityError("falhou tradeitem_one_active_per_instance, sem aspas nem 'constraint'")

    assert services.violated_constraint(erro) is None


def test_banco_recusa_apagar_instancia_que_esta_numa_oferta(cena: SimpleNamespace) -> None:
    _item(_oferta(cena), cena.a1, ativo=True)

    with pytest.raises(ProtectedError):
        cena.a1.delete()
