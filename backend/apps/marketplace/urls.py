from django.urls import path

from .views import CancelListingView, ListingDetailView, ListingListCreateView

urlpatterns = [
    path("listings/", ListingListCreateView.as_view(), name="listing-list"),
    path("listings/<uuid:listing_id>/", ListingDetailView.as_view(), name="listing-detail"),
    path(
        "listings/<uuid:listing_id>/cancel/",
        CancelListingView.as_view(),
        name="listing-cancel",
    ),
]
