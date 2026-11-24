from typing import cast

from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.friends import selectors as friends_selectors

from . import selectors
from .serializers import MAX_PAGE_SIZE, InventoryItemSerializer, InventoryQuerySerializer


class InventoryPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE


def _eu(request: Request) -> User:
    return cast(User, request.user)


def _listar(request: Request, dono: User) -> Response:
    """Lista o inventário de `dono`. Só chamar DEPOIS de decidir que o leitor pode vê-lo."""
    consulta = InventoryQuerySerializer(data=request.query_params)
    consulta.is_valid(raise_exception=True)
    filtros = consulta.validated_data
    itens = selectors.search(
        selectors.inventory_of(dono),
        rarity=filtros.get("rarity"),
        weapon=filtros.get("weapon"),
        wear=filtros.get("wear"),
        q=filtros.get("q"),
        ordering=filtros["ordering"],
    )
    paginacao = InventoryPagination()
    pagina = paginacao.paginate_queryset(itens, request)
    return paginacao.get_paginated_response(InventoryItemSerializer(pagina, many=True).data)


class MyInventoryView(APIView):
    """O meu inventário."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        return _listar(request, _eu(request))


class UserInventoryView(APIView):
    """O inventário de um jogador: o meu ou o de um amigo aceito, via `can_view`.

    Quem não pode ver, e usuário inexistente, recebem o MESMO 404 (nunca 403, que confirmaria
    que o jogador existe). A autorização vem ANTES de validar a query: um 400 só chega a quem
    já pode ver, senão o código de status denunciaria a amizade.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request, username: str) -> Response:
        dono = friends_selectors.find_user(username)
        if dono is None or not friends_selectors.can_view(_eu(request), dono):
            raise PermissionDenied
        return _listar(request, dono)
