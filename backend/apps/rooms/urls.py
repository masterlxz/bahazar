from django.urls import path

from .views import LeaveRoomView, RoomDetailView, RoomListCreateView

urlpatterns = [
    path("rooms/", RoomListCreateView.as_view(), name="room-list"),
    path("rooms/<uuid:room_id>/", RoomDetailView.as_view(), name="room-detail"),
    path("rooms/<uuid:room_id>/leave/", LeaveRoomView.as_view(), name="room-leave"),
]
