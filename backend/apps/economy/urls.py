from django.urls import path

from .views import DailyClaimView, WalletView

urlpatterns = [
    path("wallet/", WalletView.as_view(), name="wallet"),
    path("wallet/daily/", DailyClaimView.as_view(), name="wallet-daily"),
]
