"""Views do catálogo de skins: listagem, detalhe e facetas.

API pública (sem autenticação), somente leitura.
"""

import uuid
from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.catalog import selectors
from apps.catalog.models import Skin
from apps.catalog.serializers import SkinDetailSerializer, SkinListSerializer


class CatalogPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 100


class SkinViewSet(ReadOnlyModelViewSet):
    """CRUD somente leitura do catálogo: list e retrieve."""

    pagination_class = CatalogPagination
    # Sem permission_classes: público
    http_method_names = ["get", "head", "options"]

    def get_queryset(self) -> "QuerySet[Skin]":
        """QuerySet base: skins ativas, ordenadas por nome (padrão)."""
        return Skin.objects.filter(active=True).order_by("name", "id")

    def get_serializer_class(self) -> type[SkinListSerializer | SkinDetailSerializer]:
        if self.action == "retrieve":
            return SkinDetailSerializer
        return SkinListSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /api/v1/catalog/skins/ com query params de filtro e paginação."""
        # Valida params de query
        rarity = request.query_params.get("rarity") or None
        weapon = request.query_params.get("weapon") or None
        collection = request.query_params.get("collection") or None
        wear_param = request.query_params.get("wear")
        wear = [w.strip() for w in wear_param.split(",")] if wear_param else None
        q = request.query_params.get("q") or None
        ordering = request.query_params.get("ordering", selectors.DEFAULT_ORDERING)

        # Valida ordering
        if ordering not in selectors.ORDERING_CHOICES:
            return Response(
                {"code": "invalid_ordering", "message": f"Ordenação inválida: {ordering}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = selectors.search(
            rarity=rarity,
            weapon=weapon,
            collection=collection,
            wear=wear,
            q=q,
            ordering=ordering,
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /api/v1/catalog/skins/<uuid>/

        Retorna 404 padronizado se não encontrado ou inativo.
        """
        try:
            skin_id = uuid.UUID(kwargs["pk"])
        except ValueError:
            return Response(
                {"code": "not_found", "message": "Não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        skin = selectors.get(skin_id)
        if skin is None:
            return Response(
                {"code": "not_found", "message": "Não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(skin)
        return Response(serializer.data)


class FacetsViewSet(ReadOnlyModelViewSet):
    """GET /api/v1/catalog/skins/facets/ - valores únicos para selects do frontend."""

    http_method_names = ["get", "head", "options"]
    pagination_class = None  # sem paginação

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Valores únicos respeitando os mesmos filtros da listagem."""
        rarity = request.query_params.get("rarity") or None
        weapon = request.query_params.get("weapon") or None
        collection = request.query_params.get("collection") or None
        wear_param = request.query_params.get("wear")
        wear = [w.strip() for w in wear_param.split(",")] if wear_param else None
        q = request.query_params.get("q") or None

        data = selectors.facets(
            rarity=rarity,
            weapon=weapon,
            collection=collection,
            wear=wear,
            q=q,
        )
        return Response(data)
