"""URLconf só de teste: uma view que NÃO declara permissão, para provar o padrão negar."""

from django.http import HttpRequest
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView


class SemPermissaoExplicita(APIView):
    def get(self, request: HttpRequest) -> Response:
        return Response({"segredo": "não deveria vazar"})


urlpatterns = [path("sem-permissao/", SemPermissaoExplicita.as_view())]
