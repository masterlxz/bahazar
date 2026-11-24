from django.urls import include, path

urlpatterns = [
    path("_allauth/", include("allauth.headless.urls")),
    path("accounts/", include("allauth.urls")),  # nomes de URL que o allauth resolve por dentro
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.rooms.urls")),
    path("api/v1/", include("apps.economy.urls")),
    path("api/v1/", include("apps.friends.urls")),
    path("api/v1/", include("apps.inventory.urls")),
]
