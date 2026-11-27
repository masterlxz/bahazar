import uuid
from typing import cast

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User

from . import selectors, services
from .serializers import FriendSerializer, FriendshipSerializer

_USERNAME_MAX = 20


def _eu(request: Request) -> User:
    return cast(User, request.user)


def _conflito(erro: services.FriendshipError) -> Response:
    return Response({"code": erro.code, "message": erro.message}, status=status.HTTP_409_CONFLICT)


class FriendListView(APIView):
    """Meus amigos aceitos."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        return Response(FriendSerializer(selectors.friends_of(_eu(request)), many=True).data)


class ReceivedRequestsView(APIView):
    """Pedidos que recebi e ainda não respondi (GET) e enviar um pedido (POST)."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request: Request) -> Response:
        pedidos = selectors.received_requests(_eu(request))
        return Response(FriendshipSerializer(pedidos, many=True).data)

    def post(self, request: Request) -> Response:
        dados = request.data
        username = dados.get("username") if hasattr(dados, "get") else None
        if not isinstance(username, str) or not 0 < len(username.strip()) <= _USERNAME_MAX:
            return Response(
                {"code": "invalid_username", "message": "Informe o nome de usuário."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pedido = services.send_request(_eu(request), username)
        except services.FriendshipError as erro:
            return _conflito(erro)
        return Response(FriendshipSerializer(pedido).data, status=status.HTTP_201_CREATED)


class SentRequestsView(APIView):
    """Pedidos que enviei e ainda não foram respondidos."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        pedidos = selectors.sent_requests(_eu(request))
        return Response(FriendshipSerializer(pedidos, many=True).data)


class AcceptRequestView(APIView):
    """Aceita um pedido recebido. Quem não é o destinatário recebe 404."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["post", "options"]

    def post(self, request: Request, request_id: uuid.UUID) -> Response:
        try:
            pedido = services.accept_request(_eu(request), request_id)
        except services.NotFound:
            raise Http404 from None
        return Response(FriendshipSerializer(pedido).data)


class DeclineRequestView(APIView):
    """Recusa um pedido recebido: apaga a linha. Quem não é o destinatário recebe 404."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["post", "options"]

    def post(self, request: Request, request_id: uuid.UUID) -> Response:
        try:
            services.decline_request(_eu(request), request_id)
        except services.NotFound:
            raise Http404 from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendDetailView(APIView):
    """Perfil de um amigo (GET, via `can_view`) e remover amizade (DELETE).

    Sem permissão de visibilidade, o GET dá o mesmo 404 de "usuário não existe".
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "delete", "head", "options"]

    def get(self, request: Request, username: str) -> Response:
        dono = selectors.find_user(username)
        if dono is None or not selectors.can_view(_eu(request), dono):
            raise Http404
        return Response(FriendSerializer(dono).data)

    def delete(self, request: Request, username: str) -> Response:
        try:
            services.remove_friend(_eu(request), username)
        except services.NotFound:
            raise Http404 from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockedListView(APIView):
    """Quem eu bloqueei (só leitura). Quem me bloqueou nunca aparece."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        return Response(FriendSerializer(selectors.blocked_by(_eu(request)), many=True).data)


class BlockView(APIView):
    """Bloquear (POST) e desbloquear (DELETE). Só o bloqueador desbloqueia."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "friend_block"
    http_method_names = ["post", "delete", "options"]

    def get_throttles(self) -> list[BaseThrottle]:
        """Só o POST gasta a cota: bloquear cancela as ofertas do par (escrita com trava).

        `ScopedRateThrottle` vale para a view inteira; sem esta troca, desbloquear gastaria a
        cota de bloquear.
        """
        return super().get_throttles() if self.request.method == "POST" else []

    def post(self, request: Request, username: str) -> Response:
        try:
            services.block(_eu(request), username)
        except services.NotFound:
            raise Http404 from None
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, username: str) -> Response:
        try:
            services.unblock(_eu(request), username)
        except services.NotFound:
            raise Http404 from None
        return Response(status=status.HTTP_204_NO_CONTENT)
