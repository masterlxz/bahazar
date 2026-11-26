"""Rotas dos anúncios do mercado: criar, cancelar, listar e ler."""

import uuid
from typing import cast

from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User

from . import selectors, services
from .models import MarketListing
from .serializers import InvalidInput, ListingSerializer, parse_create_body

# Erro do serviço -> status HTTP. O mapa é exato por classe: um erro novo sem status vira 500.
_STATUS_DO_ERRO: dict[type[services.MarketError], int] = {
    services.InstanceNotFound: status.HTTP_404_NOT_FOUND,
    services.ItemConsumed: status.HTTP_409_CONFLICT,
    services.ItemAlreadyListed: status.HTTP_409_CONFLICT,
    services.ItemLocked: status.HTTP_409_CONFLICT,
    services.ListingNotFound: status.HTTP_404_NOT_FOUND,
    services.ListingNotActive: status.HTTP_409_CONFLICT,
}


def _eu(request: Request) -> User:
    return cast(User, request.user)


def _erro(code: str, message: str, http_status: int) -> Response:
    return Response({"code": code, "message": message}, status=http_status)


def _erro_do_servico(erro: services.MarketError) -> Response:
    return _erro(erro.code, erro.message, _STATUS_DO_ERRO[type(erro)])


def _listing_data(listing: MarketListing) -> dict[str, object]:
    """O anúncio no formato público da API."""
    return dict(ListingSerializer(listing).data)


class ListingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ListingListCreateView(APIView):
    """GET: os anúncios ativos da vitrine. POST: anuncia um item do jogador."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "market_listing_create"
    http_method_names = ["get", "post", "head", "options"]

    def get_throttles(self) -> list[BaseThrottle]:
        """Escopo por método: só o POST gasta a cota de criar; a leitura tem a sua.

        `ScopedRateThrottle` vale para a view inteira. Sem esta troca, a vitrine (GET) esgotaria
        a cota de anunciar (POST) do mesmo jogador.
        """
        self.throttle_scope = (
            "market_listing_create" if self.request.method == "POST" else "market_listing_read"
        )
        return super().get_throttles()

    def get(self, request: Request) -> Response:
        paginacao = ListingPagination()
        pagina = paginacao.paginate_queryset(selectors.active_listings(), request)
        if pagina is None:
            raise RuntimeError("ListingPagination precisa de page_size")
        return paginacao.get_paginated_response(ListingSerializer(pagina, many=True).data)

    def post(self, request: Request) -> Response:
        try:
            dados = parse_create_body(request.data)
        except ParseError:
            return _erro(
                "invalid_body",
                "O corpo precisa ser um objeto JSON.",
                status.HTTP_400_BAD_REQUEST,
            )
        except InvalidInput as erro:
            return _erro(erro.code, erro.message, status.HTTP_400_BAD_REQUEST)
        try:
            anuncio = services.create_listing(_eu(request), dados.instance_id, dados.price)
        except services.MarketError as erro:
            return _erro_do_servico(erro)
        return Response(_listing_data(anuncio), status=status.HTTP_201_CREATED)


class ListingDetailView(APIView):
    """Um anúncio ativo. Anúncio fechado ou inexistente dá o mesmo 404."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "market_listing_read"
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request, listing_id: uuid.UUID) -> Response:
        anuncio = selectors.active_listing(listing_id)
        if anuncio is None:
            return _erro(
                services.ListingNotFound.code,
                services.ListingNotFound.message,
                status.HTTP_404_NOT_FOUND,
            )
        return Response(_listing_data(anuncio))


class CancelListingView(APIView):
    """Cancela um anúncio ativo do vendedor."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "market_listing_cancel"
    http_method_names = ["post", "options"]

    def post(self, request: Request, listing_id: uuid.UUID) -> Response:
        try:
            anuncio = services.cancel_listing(_eu(request), listing_id)
        except services.MarketError as erro:
            return _erro_do_servico(erro)
        return Response(_listing_data(anuncio), status=status.HTTP_200_OK)
