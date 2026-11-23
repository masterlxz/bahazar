"""Garantias do banco para convites: valem mesmo que a API ou um serviço tenham bug."""

import hashlib
from datetime import timedelta
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from .conftest import criar_sala_pela_api

pytestmark = pytest.mark.django_db


def _convite(sala_id: str, dono: Any, codigo: str = "abc", **extra: Any) -> Any:
    from apps.rooms.models import RoomInvite

    campos: dict[str, Any] = {
        "room_id": sala_id,
        "created_by": dono,
        "code_hash": hashlib.sha256(codigo.encode()).digest(),
        "expires_at": timezone.now() + timedelta(days=7),
        "max_uses": 10,
        "uses": 0,
    }
    campos.update(extra)
    return RoomInvite.objects.create(**campos)


def test_banco_recusa_dois_convites_com_o_mesmo_hash(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)
    _convite(sala["id"], ana, "mesmo")

    with pytest.raises(IntegrityError), transaction.atomic():
        _convite(sala["id"], ana, "mesmo")


def test_banco_recusa_mais_usos_que_o_maximo(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    with pytest.raises(IntegrityError), transaction.atomic():
        _convite(sala["id"], ana, max_uses=3, uses=4)


def test_banco_aceita_usos_iguais_ao_maximo(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    _convite(sala["id"], ana, max_uses=3, uses=3)


def test_banco_recusa_usos_negativos_e_maximo_zero(ana: Any) -> None:
    sala = criar_sala_pela_api(ana)

    with pytest.raises(IntegrityError), transaction.atomic():
        _convite(sala["id"], ana, "a", uses=-1)
    with pytest.raises(IntegrityError), transaction.atomic():
        _convite(sala["id"], ana, "b", max_uses=0, uses=0)
