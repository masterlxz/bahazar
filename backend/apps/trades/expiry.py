"""Expiração das ofertas de troca pendentes (decisão do dono, 2026-11-27).

Uma oferta `pending` com `created_at` ESTRITAMENTE anterior a `agora - N dias` vira `expired` e
solta os itens. Sem isso, um amigo seguraria para sempre os itens pedidos (o `offer_guard` os
trava para o mercado). Manual: nenhum agendamento chama isto (fica para o deploy). O prazo padrão
de 7 dias é HIPÓTESE sem fonte. Aceitar uma oferta velha continua possível até a expiração rodar.

Cada oferta expira na sua própria transação (`services.expire_offer`): uma que alguém resolveu
no meio não desfaz as outras, e rodar de novo é seguro.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from . import services
from .models import TradeOffer, TradeStatus

MAX_DAYS = 3650  # ~10 anos: teto arbitrário, muito abaixo de onde as datas estouram


def _now() -> datetime:
    """Relógio da expiração. Existe para os testes o substituírem (`monkeypatch`)."""
    return timezone.now()


def expire_offers(*, days: int, now: datetime | None = None, dry_run: bool = False) -> int:
    """Expira as pendentes com `created_at < now - days` e devolve quantas (ou quantas expiraria).

    Com `dry_run=True` só conta. Fora de `1 <= days <= MAX_DAYS` levanta `ValueError`: 0 expiraria
    tudo que está pendente agora, negativo teria o corte no futuro e um N gigante estoura com
    `OverflowError`. O total conta só as que ESTE chamador expirou: uma que outro processo
    resolveu entre a listagem e a trava não entra.
    """
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days deve estar entre 1 e {MAX_DAYS} (recebi {days})")
    corte = (now if now is not None else _now()) - timedelta(days=days)
    vencidas = TradeOffer.objects.filter(status=TradeStatus.PENDING, created_at__lte=corte)
    if dry_run:
        return vencidas.count()
    ids = list(vencidas.order_by("pk").values_list("pk", flat=True))
    return sum(1 for oferta_id in ids if services.expire_offer(oferta_id))
