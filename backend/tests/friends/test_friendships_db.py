"""Garantias do banco para amizades: valem mesmo que a API ou um serviço tenham bug."""

from typing import Any

import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def _linha(de: Any, para: Any, status: str = "pending") -> Any:
    from apps.friends.models import Friendship

    return Friendship.objects.create(requester=de, addressee=para, status=status)


def test_banco_recusa_auto_pedido(ana: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _linha(ana, ana)


def test_banco_recusa_o_mesmo_pedido_duas_vezes(ana: Any, bruno: Any) -> None:
    _linha(ana, bruno)

    with pytest.raises(IntegrityError), transaction.atomic():
        _linha(ana, bruno)


def test_banco_recusa_o_pedido_na_direcao_oposta(ana: Any, bruno: Any) -> None:
    """Uma relação por par NÃO ORDENADO: ana->bruno e bruno->ana não coexistem."""
    _linha(ana, bruno)

    with pytest.raises(IntegrityError), transaction.atomic():
        _linha(bruno, ana)


def test_banco_aceita_pares_diferentes_com_um_usuario_em_comum(
    ana: Any, bruno: Any, carla: Any
) -> None:
    _linha(ana, bruno)
    _linha(ana, carla)
    _linha(bruno, carla)


def test_banco_recusa_status_fora_da_lista(ana: Any, bruno: Any) -> None:
    linha = _linha(ana, bruno)

    with pytest.raises(IntegrityError), transaction.atomic():
        type(linha).objects.filter(pk=linha.pk).update(status="casados")
