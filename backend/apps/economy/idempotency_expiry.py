"""Expiração dos registros de idempotência (ADR 0014, pendência "expiração").

Apaga os `IdempotencyRecord` ESTRITAMENTE anteriores a `agora - N dias`. É dado apagado de vez:
depois que o registro some, a mesma chave volta a valer e um retry atrasado do cliente executaria
a operação outra vez. Por isso a janela tem piso (`days >= 1`) e quem chama escolhe o N.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from .models import IdempotencyRecord


def _now() -> datetime:
    """Relógio da expiração. Existe para os testes o substituírem (`monkeypatch`)."""
    return timezone.now()


def expire_records(*, days: int, now: datetime | None = None, dry_run: bool = False) -> int:
    """Apaga os registros com `created_at < now - days` e devolve quantos (ou quantos apagaria).

    Com `dry_run=True` só conta, sem apagar. `days < 1` levanta `ValueError`: 0 apagaria tudo
    (inclusive registros de agora) e negativo teria o corte no futuro.
    """
    if days < 1:
        raise ValueError(f"days deve ser um inteiro >= 1 (recebi {days})")
    corte = (now or _now()) - timedelta(days=days)
    expirados = IdempotencyRecord.objects.filter(created_at__lt=corte)
    if dry_run:
        return expirados.count()
    apagados, _ = expirados.delete()
    return apagados
