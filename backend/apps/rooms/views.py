import uuid
from typing import Any, cast

from django.db.models import QuerySet
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User

from . import rules, selectors, services
from .models import Room, RoomMember
from .permissions import IsRoomAdmin, IsRoomMember
from .serializers import InviteSerializer, MemberSerializer, RoomSerializer


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


class RoomMembersView(APIView):
    """Membros ativos da sala, para qualquer membro ativo. Não-membro: 404 (como em `rooms`)."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request, room_id: uuid.UUID) -> Response:
        sala = selectors.rooms_for_user(cast(User, request.user)).filter(pk=room_id).first()
        if sala is None:
            raise Http404
        return Response(MemberSerializer(selectors.members_of(sala), many=True).data)


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


def _sala_administrada(request: Request, room_id: uuid.UUID) -> Room:
    """A sala, se quem pergunta é dono ou administrador. Não-membro: 404; membro comum: 403."""
    sala = selectors.rooms_for_user(cast(User, request.user)).filter(pk=room_id).first()
    if sala is None:
        raise Http404
    if not rules.is_room_admin(getattr(sala, "my_role", None)):
        raise PermissionDenied
    return sala


def _inteiro_opcional(dados: Any, campo: str) -> int | None:
    valor = dados.get(campo) if isinstance(dados, dict) else None
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValidationError({campo: ["Informe um número inteiro."]})
    return valor


class InviteListCreateView(APIView):
    """Convites da sala (GET) e criar convite (POST). Só dono ou administrador."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request: Request, room_id: uuid.UUID) -> Response:
        sala = _sala_administrada(request, room_id)
        return Response(InviteSerializer(selectors.invites_of_room(sala), many=True).data)

    def post(self, request: Request, room_id: uuid.UUID) -> Response:
        sala = _sala_administrada(request, room_id)
        dias = _inteiro_opcional(request.data, "expires_in_days")
        usos = _inteiro_opcional(request.data, "max_uses")
        try:
            convite, codigo = services.create_invite(
                cast(User, request.user), sala.pk, expires_in_days=dias, max_uses=usos
            )
        except services.InvalidInvitePolicy as erro:
            return Response(
                {"code": erro.code, "message": erro.message}, status=status.HTTP_400_BAD_REQUEST
            )
        except RoomMember.DoesNotExist:
            raise Http404 from None  # saiu da sala entre a checagem da view e a do serviço
        except services.RoomError as erro:
            return _conflito(erro)
        # O código só existe aqui: nenhuma outra resposta (nem a listagem) o devolve.
        return Response(
            {**InviteSerializer(convite).data, "code": codigo}, status=status.HTTP_201_CREATED
        )


class InviteDetailView(APIView):
    """Revogar um convite da sala (DELETE). O convite é buscado dentro da sala da URL."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["delete", "options"]

    def delete(self, request: Request, room_id: uuid.UUID, invite_id: uuid.UUID) -> Response:
        sala = _sala_administrada(request, room_id)
        try:
            services.revoke_invite(cast(User, request.user), sala.pk, invite_id)
        except (services.InviteNotFound, RoomMember.DoesNotExist):
            raise Http404 from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class JoinRoomView(APIView):
    """Entrar numa sala pelo código do convite. Limitado por usuário contra força bruta."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invite_redeem"
    http_method_names = ["post", "options"]

    def post(self, request: Request) -> Response:
        dados = request.data
        codigo = dados.get("code") if isinstance(dados, dict) else None
        if not isinstance(codigo, str) or not codigo.strip():
            raise ValidationError({"code": ["Informe o código do convite."]})
        usuario = cast(User, request.user)
        try:
            sala = services.redeem_invite(usuario, codigo.strip())
        except services.InviteNotFound:
            raise Http404 from None
        except services.RoomError as erro:
            return _conflito(erro)
        visao = selectors.rooms_for_user(usuario).get(pk=sala.pk)
        return Response(RoomSerializer(visao).data)
