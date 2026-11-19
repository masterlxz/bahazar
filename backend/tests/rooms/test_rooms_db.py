"""Garantias do banco para salas e membros: valem mesmo que a API ou um serviço tenham bug."""

from typing import Any

import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def _sala(dono: Any) -> Any:
    from apps.rooms.models import Room, RoomMember

    sala = Room.objects.create(name="Amigos", owner=dono)
    RoomMember.objects.create(room=sala, user=dono, role="owner", status="active")
    return sala


def test_banco_recusa_segundo_dono_ativo_na_mesma_sala(ana: Any, bruno: Any) -> None:
    from apps.rooms.models import RoomMember

    sala = _sala(ana)

    with pytest.raises(IntegrityError), transaction.atomic():
        RoomMember.objects.create(room=sala, user=bruno, role="owner", status="active")


def test_banco_recusa_o_mesmo_usuario_duas_vezes_na_sala(ana: Any) -> None:
    from apps.rooms.models import RoomMember

    sala = _sala(ana)

    with pytest.raises(IntegrityError), transaction.atomic():
        RoomMember.objects.create(room=sala, user=ana, role="member", status="active")


def test_banco_recusa_papel_ou_visibilidade_fora_da_lista(ana: Any) -> None:
    from apps.rooms.models import Room, RoomMember

    sala = _sala(ana)

    with pytest.raises(IntegrityError), transaction.atomic():
        RoomMember.objects.filter(room=sala, user=ana).update(role="deus")
    with pytest.raises(IntegrityError), transaction.atomic():
        Room.objects.filter(id=sala.id).update(visibility="secreta")


def test_dono_que_saiu_nao_conta_como_dono_ativo(ana: Any, bruno: Any) -> None:
    """O índice único é parcial (status ativo): quem saiu não bloqueia um novo dono."""
    from apps.rooms.models import RoomMember

    sala = _sala(ana)
    RoomMember.objects.filter(room=sala, user=ana).update(status="left")

    RoomMember.objects.create(room=sala, user=bruno, role="owner", status="active")

    assert RoomMember.objects.filter(room=sala, role="owner", status="active").count() == 1
