"""Auditoria do ledger: as invariantes de MODELO-DE-DADOS §4. Lista vazia = tudo certo."""

from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from .models import Wallet, WalletKind, WalletTransaction


def check_ledger() -> list[str]:
    problemas: list[str] = []

    total = WalletTransaction.objects.aggregate(t=Sum("amount"))["t"] or 0
    if total != 0:
        problemas.append(f"soma global do ledger = {total} (esperado 0)")

    por_grupo = (
        WalletTransaction.objects.values("group_id").annotate(soma=Sum("amount")).exclude(soma=0)
    )
    for grupo in por_grupo:
        problemas.append(f"lançamento {grupo['group_id']} soma {grupo['soma']} (esperado 0)")

    divergentes = (
        Wallet.objects.annotate(soma=Coalesce(Sum("transactions__amount"), 0))
        .exclude(balance=F("soma"))
        .values("id", "balance", "soma")
    )
    for carteira in divergentes:
        problemas.append(
            f"carteira {carteira['id']}: saldo {carteira['balance']} "
            f"difere da soma do extrato {carteira['soma']}"
        )

    negativas = Wallet.objects.filter(kind=WalletKind.PLAYER, balance__lt=0).values_list(
        "id", flat=True
    )
    for carteira_id in negativas:
        problemas.append(f"carteira de jogador {carteira_id} com saldo negativo")

    return problemas
