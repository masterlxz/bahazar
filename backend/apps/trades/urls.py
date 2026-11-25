from django.urls import path

from .views import (
    AcceptOfferView,
    CancelOfferView,
    DeclineOfferView,
    TradeDetailView,
    TradeListCreateView,
)

urlpatterns = [
    path("trades/", TradeListCreateView.as_view(), name="trade-list"),
    path("trades/<uuid:offer_id>/", TradeDetailView.as_view(), name="trade-detail"),
    path("trades/<uuid:offer_id>/accept/", AcceptOfferView.as_view(), name="trade-accept"),
    path("trades/<uuid:offer_id>/decline/", DeclineOfferView.as_view(), name="trade-decline"),
    path("trades/<uuid:offer_id>/cancel/", CancelOfferView.as_view(), name="trade-cancel"),
]
