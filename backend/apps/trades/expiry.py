"""Esqueleto do controle (Sessão 49): sem implementação, os testes falham pelo motivo certo."""

from datetime import datetime

from django.utils import timezone

MAX_DAYS = 3650


def _now() -> datetime:
    return timezone.now()


def expire_offers(*, days: int, now: datetime | None = None, dry_run: bool = False) -> int:
    raise NotImplementedError
