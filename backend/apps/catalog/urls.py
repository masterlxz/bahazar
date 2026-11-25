"""URLs do catálogo de skins."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import FacetsViewSet, SkinViewSet

router = DefaultRouter()
router.register(r"skins", SkinViewSet, basename="skin")

# Facets como endpoint extra do router (não é um ViewSet padrão de CRUD)
urlpatterns = [
    path("", include(router.urls)),
    path("skins/facets/", FacetsViewSet.as_view({"get": "list"}), name="skin-facets"),
]