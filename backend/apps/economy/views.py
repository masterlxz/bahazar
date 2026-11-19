from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


def _diaria(estado: services.WalletStatus) -> dict[str, Any]:
    return {
        "can_claim": estado.can_claim,
        "available_at": estado.available_at.isoformat() if estado.available_at else None,
        "next_streak_day": estado.next_streak_day,
        "next_amount": estado.next_amount,
    }


class WalletView(APIView):
    """A carteira do próprio usuário: saldo e situação da diária. Só leitura, sem id na URL."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        estado = services.get_wallet_status(request.user)
        return Response({"balance": estado.balance, "daily": _diaria(estado)})


class DailyClaimView(APIView):
    """Resgata a diária. O corpo é ignorado: valor e sequência vêm sempre do servidor."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["post", "options"]

    def post(self, request: Request) -> Response:
        try:
            resgate = services.claim_daily(request.user)
        except services.DailyNotReady as erro:
            return Response(
                {
                    "code": erro.code,
                    "message": erro.message,
                    "available_at": erro.available_at.isoformat(),
                },
                status=status.HTTP_409_CONFLICT,
            )
        estado = services.get_wallet_status(request.user, now=resgate.claimed_at)
        return Response(
            {
                "amount": resgate.amount,
                "streak_day": resgate.streak_day,
                "balance": estado.balance,
                "next_available_at": estado.available_at.isoformat()
                if estado.available_at
                else None,
            },
            status=status.HTTP_201_CREATED,
        )
