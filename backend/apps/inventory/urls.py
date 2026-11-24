from django.urls import path

from .views import MyInventoryView, UserInventoryView

urlpatterns = [
    path("inventory/", MyInventoryView.as_view(), name="inventory"),
    path("inventory/<str:username>/", UserInventoryView.as_view(), name="inventory-user"),
]
