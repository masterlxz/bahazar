"""STUB do commit só-de-teste: não apaga nada. A implementação vem no commit seguinte."""

from datetime import datetime

from django.utils import timezone


def _now() -> datetime:
    return timezone.now()


def expire_records(*, days: int, now: datetime | None = None, dry_run: bool = False) -> int:
    return 0
