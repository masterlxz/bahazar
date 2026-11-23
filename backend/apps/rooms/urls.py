from django.urls import path

from .views import (
    InviteDetailView,
    InviteListCreateView,
    JoinRoomView,
    LeaveRoomView,
    RoomDetailView,
    RoomListCreateView,
)

urlpatterns = [
    path("rooms/", RoomListCreateView.as_view(), name="room-list"),
    path("rooms/join/", JoinRoomView.as_view(), name="room-join"),
    path("rooms/<uuid:room_id>/invites/", InviteListCreateView.as_view(), name="room-invites"),
    path(
        "rooms/<uuid:room_id>/invites/<uuid:invite_id>/",
        InviteDetailView.as_view(),
        name="room-invite-detail",
    ),
    path("rooms/<uuid:room_id>/", RoomDetailView.as_view(), name="room-detail"),
    path("rooms/<uuid:room_id>/leave/", LeaveRoomView.as_view(), name="room-leave"),
]
