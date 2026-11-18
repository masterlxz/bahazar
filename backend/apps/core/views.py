from django.db import OperationalError, connection
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness + acesso ao banco. Pública de propósito (monitoramento); não expõe dado algum."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError:
            return Response({"status": "degraded", "database": "error"}, status=503)
        return Response({"status": "ok", "database": "ok"})
