"""Expiração dos registros de idempotência (ADR 0014, pendência "expiração").

Apaga os `IdempotencyRecord` ESTRITAMENTE anteriores a `agora - N dias`. É dado apagado de vez:
depois que o registro some, a mesma chave volta a valer e um retry atrasado do cliente executaria
a operação outra vez.

O N escolhido tem de ser MAIOR que a maior janela de retry do cliente (hipótese: 7 dias, sem fonte
no projeto); nada no código garante isso. Os limites `1 <= days <= MAX_DAYS` NÃO protegem contra
isso: o piso só evita apagar tudo (0) ou cortar no futuro (negativo), e o teto evita o
`OverflowError` de um N absurdo.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from .models import IdempotencyRecord

MAX_DAYS = 3650  # ~10 anos: teto arbitrário, muito abaixo de onde as datas estouram


def _now() -> datetime:
    """Relógio da expiração. Existe para os testes o substituírem (`monkeypatch`)."""
    return timezone.now()


def expire_records(*, days: int, now: datetime | None = None, dry_run: bool = False) -> int:
    """Apaga os registros com `created_at < now - days` e devolve quantos (ou quantos apagaria).

    Com `dry_run=True` só conta, sem apagar. Fora de `1 <= days <= MAX_DAYS` levanta `ValueError`:
    0 apagaria tudo que existe até agora, negativo teria o corte no futuro e um N gigante
    estoura com `OverflowError`.
    """
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days deve estar entre 1 e {MAX_DAYS} (recebi {days})")
    corte = (now if now is not None else _now()) - timedelta(days=days)
    expirados = IdempotencyRecord.objects.filter(created_at__lte=corte)
    if dry_run:
        return expirados.count()
    apagados, _ = expirados.delete()
    return apagados
