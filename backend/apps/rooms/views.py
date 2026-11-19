import uuid
from typing import Any, cast

from django.db.models import QuerySet
from django.http import Http404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from . import selectors, services
from .models import Room, RoomMember
from .permissions import IsRoomAdmin, IsRoomMember
from .serializers import RoomSerializer


def _conflito(erro: services.RoomError) -> Response:
    return Response({"code": erro.code, "message": erro.message}, status=status.HTTP_409_CONFLICT)


class RoomListCreateView(ListCreateAPIView):
    """Minhas salas (GET) e criar sala (POST)."""

    permission_classes = [IsAuthenticated]
    serializer_class = RoomSerializer

    def get_queryset(self) -> QuerySet[Room]:
        return selectors.rooms_for_user(cast(User, self.request.user))

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        usuario = cast(User, request.user)
        try:
            sala = services.create_room(usuario, entrada.validated_data["name"])
        except services.RoomError as erro:
            return _conflito(erro)
        # Relê pelo seletor: a resposta traz o papel (`role`) como qualquer outra leitura.
        criada = selectors.rooms_for_user(usuario).get(pk=sala.pk)
        return Response(self.get_serializer(criada).data, status=status.HTTP_201_CREATED)


class RoomDetailView(RetrieveUpdateAPIView):
    """Detalhe de uma sala (membro) e renomear (dono ou administrador)."""

    permission_classes = [IsAuthenticated, IsRoomMember]
    serializer_class = RoomSerializer
    lookup_url_kwarg = "room_id"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Room]:
        # Quem não é membro não vê a sala: o `get_object` dá 404, idêntico a "não existe".
        return selectors.rooms_for_user(cast(User, self.request.user))

    def get_permissions(self) -> list[Any]:
        # `Any`: o stub do DRF tipa o retorno com um protocolo privado (`_SupportsHasPermission`).
        permissoes: list[Any] = list(super().get_permissions())
        if self.request.method == "PATCH":
            permissoes.append(IsRoomAdmin())
        return permissoes


class LeaveRoomView(APIView):
    """Sair da sala. O pertencimento é revalidado no serviço, dentro da transação."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, room_id: uuid.UUID) -> Response:
        try:
            services.leave_room(cast(User, request.user), room_id)
        except RoomMember.DoesNotExist:
            raise Http404 from None
        except services.RoomError as erro:
            return _conflito(erro)
        return Response(status=status.HTTP_204_NO_CONTENT)
