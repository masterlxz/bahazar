from django.urls import path

from .views import (
    AcceptRequestView,
    BlockedListView,
    BlockView,
    DeclineRequestView,
    FriendDetailView,
    FriendListView,
    ReceivedRequestsView,
    SentRequestsView,
)

# `requests/` vem antes de `<username>/`: o literal precisa ganhar do conversor.
urlpatterns = [
    # `blocks/` fica fora de `friends/`: um usuário chamado `blocked` não pode colidir com a rota.
    path("blocks/", BlockedListView.as_view(), name="blocked-list"),
    path("friends/", FriendListView.as_view(), name="friend-list"),
    path("friends/requests/", ReceivedRequestsView.as_view(), name="friend-requests"),
    path("friends/requests/sent/", SentRequestsView.as_view(), name="friend-requests-sent"),
    path(
        "friends/requests/<uuid:request_id>/accept/",
        AcceptRequestView.as_view(),
        name="friend-request-accept",
    ),
    path(
        "friends/requests/<uuid:request_id>/decline/",
        DeclineRequestView.as_view(),
        name="friend-request-decline",
    ),
    path("friends/<str:username>/block/", BlockView.as_view(), name="friend-block"),
    path("friends/<str:username>/", FriendDetailView.as_view(), name="friend-detail"),
]
