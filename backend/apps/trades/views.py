"""Rotas das trocas de itens: criar, aceitar, recusar, cancelar e ler.

Os quatro POST exigem o cabeçalho `Idempotency-Key` (um UUID gerado pelo cliente) e rodam o
serviço DENTRO de `run_once`: o registro da chave e a troca confirmam na mesma transação, e um
erro de negócio desfaz as duas (a chave não fica queimada). Esta é a ÚNICA exceção à fronteira
de `trades` com o `economy`: só este arquivo importa `economy.idempotency` e `economy.rules`
(carteira e ledger seguem proibidos; `tests/trades/test_trades_arquitetura.py` vigia isso).
"""

import uuid
from collections.abc import Callable
from typing import Any, cast

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.economy.idempotency import IdempotencyKeyReused, run_once
from apps.economy.rules import normalize_idempotency_key, request_fingerprint
from apps.friends import selectors as friends_selectors

from . import selectors, services
from .models import TradeOffer
from .serializers import InvalidInput, TradeOfferSerializer, parse_create_body

IDEMPOTENCY_HEADER = "Idempotency-Key"

# Erro do serviço -> status HTTP. Mapa exato (por classe): um erro novo que ninguém mapeou dá
# `KeyError` e vira 500, em vez de ser engolido como se fosse um erro do cliente.
_STATUS_DO_ERRO: dict[type[services.TradeError], int] = {
    services.SelfTrade: status.HTTP_400_BAD_REQUEST,
    services.EmptySide: status.HTTP_400_BAD_REQUEST,
    services.DuplicateItem: status.HTTP_400_BAD_REQUEST,
    services.InvalidItemId: status.HTTP_400_BAD_REQUEST,
    services.TooManyItems: status.HTTP_400_BAD_REQUEST,
    services.NotFriends: status.HTTP_409_CONFLICT,
    services.ItemNotOwned: status.HTTP_409_CONFLICT,
    services.ItemConsumed: status.HTTP_409_CONFLICT,
    services.ItemAlreadyOffered: status.HTTP_409_CONFLICT,
    services.OfferNotPending: status.HTTP_409_CONFLICT,
    services.TooManyPendingOffers: status.HTTP_409_CONFLICT,
    services.OfferNotFound: status.HTTP_404_NOT_FOUND,
    services.NotAllowed: status.HTTP_403_FORBIDDEN,
}

# A ação de cada rota de resolução -> o serviço que a executa.
_RESOLVEDORES: dict[str, Callable[[User, uuid.UUID], TradeOffer]] = {
    "accept": services.accept_offer,
    "decline": services.decline_offer,
    "cancel": services.cancel_offer,
}


def _eu(request: Request) -> User:
    return cast(User, request.user)


def _erro(code: str, message: str, http_status: int) -> Response:
    return Response({"code": code, "message": message}, status=http_status)


def _erro_do_servico(erro: services.TradeError) -> Response:
    return _erro(erro.code, erro.message, _STATUS_DO_ERRO[type(erro)])


def _corpo_da_oferta(eu: User, offer_id: uuid.UUID) -> dict[str, Any]:
    """A oferta como a API a mostra, relida do banco (com jogadores, itens e skins)."""
    oferta = selectors.offer_for_party(eu, offer_id)
    if oferta is None:
        raise services.OfferNotFound
    selectors.load_items([oferta])
    return dict(TradeOfferSerializer(oferta).data)


def _executar_uma_vez(
    request: Request, pedido: str, operacao: Callable[[], tuple[int, dict[str, Any]]]
) -> Response:
    """Confere o cabeçalho e roda `operacao` uma única vez por `(usuário, chave)`.

    Uma repetição devolve o corpo GRAVADO no primeiro pedido (um retrato daquele momento), sem
    executar de novo: se a oferta mudou de estado desde então, a resposta repetida não reflete
    isso (para o estado atual, `GET /trades/<id>/`). A mesma chave com outro pedido dá 422. Um
    `TradeError` passa por `run_once` (a transação desfaz, a chave não queima) e vira
    `{code, message}` aqui.
    """
    try:
        chave = normalize_idempotency_key(request.headers.get(IDEMPOTENCY_HEADER) or str(uuid.uuid4()))
    except ValueError:
        return _erro(
            "invalid_idempotency_key",
            f"Envie o cabeçalho {IDEMPOTENCY_HEADER} com um UUID.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        saida = run_once(
            scope=f"user:{_eu(request).pk}", key=chave, request_hash=pedido, operation=operacao
        )
    except IdempotencyKeyReused as erro:
        return _erro(erro.code, erro.message, status.HTTP_422_UNPROCESSABLE_ENTITY)
    except services.TradeError as erro:
        return _erro_do_servico(erro)
    return Response(saida.body, status=saida.status)


def _destinatario(username: str) -> User:
    """O jogador de `username`; se não existe, um `User` NÃO gravado, só com um id novo.

    Assim, destinatário inexistente e destinatário que não é amigo percorrem o MESMO caminho do
    serviço (mesmas checagens, na mesma ordem) e dão a mesma resposta: a API não revela quais
    nomes existem. O id novo nunca coincide com o de ninguém, então o serviço acaba em
    `NotFriends` (a amizade é consultada pelo id) sem gravar nada.
    """
    return friends_selectors.find_user(username) or User(pk=uuid.uuid4())


class TradePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TradeListCreateView(APIView):
    """GET: as ofertas de que faço parte (mais novas primeiro). POST: propor uma troca."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request: Request) -> Response:
        paginacao = TradePagination()
        pagina = paginacao.paginate_queryset(selectors.offers_of(_eu(request)), request)
        if pagina is None:  # só se a paginação estiver desligada (`page_size = None`)
            raise RuntimeError("TradePagination precisa de page_size")
        selectors.load_items(pagina)
        return paginacao.get_paginated_response(TradeOfferSerializer(pagina, many=True).data)

    def post(self, request: Request) -> Response:
        try:
            dados = parse_create_body(request.data)
        except InvalidInput as erro:
            return _erro(erro.code, erro.message, status.HTTP_400_BAD_REQUEST)
        eu = _eu(request)
        # A ordem dos ids no corpo não muda o pedido: as listas entram ordenadas no hash.
        pedido = request_fingerprint(
            "trade.create",
            dados.recipient,
            sorted(str(i) for i in dados.offered),
            sorted(str(i) for i in dados.requested),
        )

        def operar() -> tuple[int, dict[str, Any]]:
            oferta = services.create_offer(
                eu, _destinatario(dados.recipient), dados.offered, dados.requested
            )
            return status.HTTP_201_CREATED, _corpo_da_oferta(eu, oferta.pk)

        return _executar_uma_vez(request, pedido, operar)


class TradeDetailView(APIView):
    """Uma oferta. Quem não faz parte dela recebe o mesmo 404 de uma oferta que não existe."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request, offer_id: uuid.UUID) -> Response:
        try:
            return Response(_corpo_da_oferta(_eu(request), offer_id))
        except services.OfferNotFound as erro:
            return _erro_do_servico(erro)


class _ResolveOfferView(APIView):
    """Base de aceitar, recusar e cancelar: muda só a ação (`trade_action`)."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["post", "options"]
    trade_action: str

    def post(self, request: Request, offer_id: uuid.UUID) -> Response:
        eu = _eu(request)
        resolver = _RESOLVEDORES[self.trade_action]
        pedido = request_fingerprint(f"trade.{self.trade_action}", str(offer_id))

        def operar() -> tuple[int, dict[str, Any]]:
            oferta = resolver(eu, offer_id)
            return status.HTTP_200_OK, _corpo_da_oferta(eu, oferta.pk)

        return _executar_uma_vez(request, pedido, operar)


class AcceptOfferView(_ResolveOfferView):
    """O destinatário aceita: os donos dos itens trocam na mesma transação do registro."""

    trade_action = "accept"


class DeclineOfferView(_ResolveOfferView):
    """O destinatário recusa: nada muda de dono e as instâncias ficam livres."""

    trade_action = "decline"


class CancelOfferView(_ResolveOfferView):
    """O proponente cancela: nada muda de dono e as instâncias ficam livres."""

    trade_action = "cancel"
