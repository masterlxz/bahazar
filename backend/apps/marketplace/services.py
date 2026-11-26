"""Regras transacionais dos anúncios: criar, cancelar e comprar, sempre sob trava.

A compra é a única operação do mercado que fala com o dinheiro. A ponte com `economy` mora só
neste arquivo e só nestes três módulos (ADR 0018; o teste de arquitetura a impõe). A ordem de
trava é a do ADR 0016: jogadores, anúncio, instância, carteiras.
"""

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.economy.idempotency import IdempotencyKeyReused as EconomyKeyReused
from apps.economy.idempotency import run_once
from apps.economy.rules import normalize_idempotency_key, request_fingerprint
from apps.economy.services import Entry, ensure_wallet, get_system_wallet, post_entries
from apps.economy.services import InsufficientFunds as EconomyInsufficientFunds
from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance

from . import rules, selectors
from .models import ListingStatus, MarketListing, MarketTransaction
from .serializers import ListingSerializer

_ONE_ACTIVE_PER_INSTANCE = "marketlist_one_active_instance"

# Tipos de linha do ledger (os valores de `economy.models.TransactionKind`, que este módulo não
# pode importar). O banco recusa um tipo que não exista (`wallettx_kind_valid`).
_LEDGER_COMPRA = "market_purchase"
_LEDGER_VENDA = "market_sale"
_LEDGER_TAXA = "market_fee"


class MarketError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "market_error"
    message = "Operação não permitida."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class InstanceNotFound(MarketError):
    """O item não existe ou não pertence ao vendedor."""

    code = "instance_not_found"
    message = "Não encontrado."


class ItemConsumed(MarketError):
    code = "item_consumed"
    message = "O item já saiu do jogo."


class ItemAlreadyListed(MarketError):
    code = "item_already_listed"
    message = "Este item já está anunciado."


class ItemLocked(MarketError):
    code = "item_locked"
    message = "O item está travado por outra operação e não pode ser anunciado."


class ListingNotFound(MarketError):
    """O anúncio não existe ou não pertence a quem tenta cancelá-lo."""

    code = "listing_not_found"
    message = "Não encontrado."


class ListingNotActive(MarketError):
    code = "listing_not_active"
    message = "Este anúncio não está ativo."


_CONSTRAINT_NO_TEXTO = re.compile(r'constraint "([^"]+)"')


def violated_constraint(erro: IntegrityError) -> str | None:
    """O nome da constraint que o banco acusou, ou `None` se não der para saber."""
    diag = getattr(erro.__cause__, "diag", None)
    nome = getattr(diag, "constraint_name", None)
    if nome:
        return str(nome)
    achado = _CONSTRAINT_NO_TEXTO.search(str(erro))
    return achado.group(1) if achado else None


@dataclass(frozen=True)
class ListingOutcome:
    """Resposta de criar ou cancelar: o corpo gravado (JSON), o status HTTP e se foi repetição."""

    body: dict[str, Any]
    status: int
    replayed: bool


def _uma_vez(
    user: User,
    idempotency_key: str,
    pedido: str,
    operacao: Callable[[], tuple[int, dict[str, Any]]],
) -> ListingOutcome:
    """Valida a chave e roda `operacao` uma única vez por `(jogador, chave)` (ADR 0014).

    O registro da chave e a operação confirmam na mesma transação: se a operação levanta um
    `MarketError`, tudo desfaz e a chave não fica queimada. A repetição devolve o corpo GRAVADO
    na primeira vez (um retrato daquele momento), sem executar de novo.
    """
    try:
        chave = normalize_idempotency_key(idempotency_key)
    except ValueError as erro:
        raise InvalidIdempotencyKey from erro
    try:
        saida = run_once(
            scope=f"user:{user.pk}", key=chave, request_hash=pedido, operation=operacao
        )
    except EconomyKeyReused as erro:
        raise IdempotencyKeyReused from erro
    return ListingOutcome(saida.body, saida.status, saida.replayed)


def _corpo(anuncio: MarketListing) -> dict[str, Any]:
    """O anúncio no formato público da API, já em tipos de JSON (é o que `run_once` grava)."""
    return dict(ListingSerializer(anuncio).data)


def create_listing(
    seller: User, instance_id: uuid.UUID, price: int, *, idempotency_key: str
) -> ListingOutcome:
    """Cria um anúncio, uma única vez por `(vendedor, chave)`; a repetição devolve o 201 gravado.

    Erros: `InvalidIdempotencyKey`, `IdempotencyKeyReused` (mesma chave, outro item ou preço) e os
    de `_gravar_anuncio`. Depois que o registro da chave expira (`expire_idempotency`), o mesmo
    pedido volta a criar um anúncio: não há guarda durável para o criar (decisão do dono,
    2026-11-26; ao contrário da compra, que tem `UNIQUE(listing)`).
    """
    pedido = request_fingerprint("market_create", str(seller.pk), str(instance_id), price)

    def operar() -> tuple[int, dict[str, Any]]:
        return 201, _corpo(_gravar_anuncio(seller, instance_id, price))

    return _uma_vez(seller, idempotency_key, pedido, operar)


def cancel_listing(user: User, listing_id: uuid.UUID, *, idempotency_key: str) -> ListingOutcome:
    """Cancela um anúncio, uma única vez por `(vendedor, chave)`; a repetição devolve o 200 gravado.

    Erros: `InvalidIdempotencyKey`, `IdempotencyKeyReused` e os de `_fechar_anuncio`. Cancelar com
    OUTRA chave um anúncio já fechado continua dando `ListingNotActive` (409): a guarda durável
    do cancelar é o estado do anúncio.
    """
    pedido = request_fingerprint("market_cancel", str(user.pk), str(listing_id))

    def operar() -> tuple[int, dict[str, Any]]:
        try:
            return 200, _corpo(_fechar_anuncio(user, listing_id))
        except ListingNotFound as erro:
            return 404, {"code": erro.code, "message": erro.message}

    return _uma_vez(user, idempotency_key, pedido, operar)


def _gravar_anuncio(seller: User, instance_id: uuid.UUID, price: int) -> MarketListing:
    """Cria um anúncio ativo para um item do vendedor.

    A instância é travada antes das conferências: só o dono pode anunciá-la, um item consumido
    não volta ao jogo e uma instância não pode ter dois anúncios ativos. Depois consulta as
    guardas de movimento: se alguma operação segura o item, o anúncio é recusado.

    O índice único parcial do banco é a rede de segurança para a corrida. Se a checagem em
    Python deixar passar, o `IntegrityError` dele vira `ItemAlreadyListed`.
    """
    try:
        with transaction.atomic():
            # O vendedor primeiro, a instância depois: a mesma ordem de `trades` (jogadores, depois
            # instâncias). O INSERT do anúncio toma `KEY SHARE` na linha do vendedor (FK), que
            # conflita com o `FOR UPDATE` que `trades` segura nos jogadores; travando a instância
            # antes, as duas transações esperariam uma pela outra (deadlock, 500 para o jogador).
            list(User.objects.select_for_update().filter(pk=seller.pk))
            instancia = SkinInstance.objects.select_for_update().filter(pk=instance_id).first()
            if instancia is None or instancia.owner_id != seller.pk:
                raise InstanceNotFound
            if instancia.consumed_at is not None:
                raise ItemConsumed
            if selectors.has_active_listing(instancia.pk):
                raise ItemAlreadyListed
            try:
                inventory_services.assert_movable(instancia)
            except inventory_services.ItemLocked as erro:
                raise ItemLocked from erro
            return MarketListing.objects.create(
                seller=seller,
                instance=instancia,
                price=price,
            )
    except IntegrityError as erro:
        if violated_constraint(erro) != _ONE_ACTIVE_PER_INSTANCE:
            raise
        raise ItemAlreadyListed from erro


def _fechar_anuncio(user: User, listing_id: uuid.UUID) -> MarketListing:
    """Cancela um anúncio ativo do vendedor.

    A linha do anúncio é travada antes de conferir dono e estado. Um anúncio de outra pessoa e
    um anúncio inexistente dão o mesmo 404; um anúncio já fechado dá 409.
    """
    with transaction.atomic():
        anuncio = MarketListing.objects.select_for_update().filter(pk=listing_id).first()
        if anuncio is None or anuncio.seller_id != user.pk:
            raise ListingNotFound
        if anuncio.status != ListingStatus.ACTIVE:
            raise ListingNotActive
        anuncio.status = ListingStatus.CANCELLED
        anuncio.closed_at = timezone.now()
        anuncio.save(update_fields=["status", "closed_at"])
        return anuncio


class CannotBuyOwnListing(MarketError):
    code = "cannot_buy_own_listing"
    message = "Você não pode comprar o seu próprio anúncio."


class ListingUnavailable(MarketError):
    """O anúncio está ativo, mas o item saiu do jogo ou já não é do vendedor."""

    code = "listing_unavailable"
    message = "O item deste anúncio não está mais disponível."


@dataclass(frozen=True)
class PurchaseResult:
    """A venda concluída. `replayed` é verdadeiro quando a mesma chave devolveu o resultado de
    uma compra já feita, sem mover nada de novo."""

    id: uuid.UUID
    listing_id: uuid.UUID
    price: int
    fee: int
    ledger_group_id: uuid.UUID
    replayed: bool


class InsufficientFunds(MarketError):
    code = "insufficient_funds"
    message = "Saldo insuficiente."


class InvalidIdempotencyKey(MarketError):
    code = "invalid_idempotency_key"
    message = "Envie o cabeçalho Idempotency-Key com um UUID."


class IdempotencyKeyReused(MarketError):
    code = "idempotency_key_reused"
    message = "Esta chave de idempotência já foi usada com outro pedido."


def _travar_jogadores(*ids: uuid.UUID) -> None:
    """Trava os jogadores por id crescente, a mesma ordem de `trades` e `friends` (ADR 0016).

    Sem o `order_by`, o PostgreSQL trava na ordem em que lê, que não é a do id.
    """
    list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def buy_listing(
    buyer: User,
    listing_id: uuid.UUID,
    *,
    idempotency_key: str,
    hide_sellers: Iterable[uuid.UUID] = (),
) -> PurchaseResult:
    """Compra o anúncio: o item, o dinheiro, a taxa e o registro da venda, tudo ou nada.

    Uma única vez por `(comprador, chave)`: repetir a chave com o mesmo pedido devolve a venda
    original (`replayed=True`) sem mover nada. A chave de negócio que sobrevive à expiração do
    registro é o `UNIQUE(listing)` de `MarketTransaction` e o estado `sold` do anúncio; por isso
    a chave de idempotência das linhas do ledger é a do ANÚNCIO, não a do cliente (a do cliente
    pode se repetir em outro anúncio depois de expirar, e o UNIQUE do ledger viraria um 500).

    `hide_sellers` são os vendedores que o comprador bloqueou (a view os lê do `friends`): o
    anúncio deles dá o mesmo 404 de anúncio inexistente. A chave é validada ANTES disso, para que
    a ordem das checagens não revele o bloqueio. Replay de uma compra de vendedor que o comprador
    bloqueou depois também dá 404, não o recibo.

    Fluxo: lê o anúncio SEM trava só para saber quem é o vendedor (as carteiras abrem antes da
    transação: `open_wallet` trava a `system`, e isso fora de ordem poderia travar uma compra
    contra outra); depois, dentro da transação, trava jogadores, anúncio e instância e SÓ ENTÃO
    confere o estado (ativo, dono, consumo), porque a leitura anterior pode estar velha. O dono
    muda antes do lançamento no ledger para que a instância fique travada antes das carteiras.

    Erros: `InvalidIdempotencyKey`, `ListingNotFound`, `CannotBuyOwnListing`, `ListingNotActive`,
    `ListingUnavailable`, `InsufficientFunds` e `IdempotencyKeyReused`. Qualquer erro do
    `inventory` na troca de dono, e um preço fora do limite gravado direto no banco, viram
    `ListingUnavailable`: o item não pode ser vendido, e nada além disso é revelado.
    """
    try:
        chave = normalize_idempotency_key(idempotency_key)
    except ValueError as erro:
        raise InvalidIdempotencyKey from erro
    if selectors.is_hidden(listing_id, hide_sellers):
        raise ListingNotFound
    previa = MarketListing.objects.select_related("seller").filter(pk=listing_id).first()
    if previa is None:
        raise ListingNotFound
    vendedor = previa.seller
    if vendedor.pk == buyer.pk:
        raise CannotBuyOwnListing
    pedido = request_fingerprint("market_buy", str(buyer.pk), str(listing_id))
    origem, destino, sistema = ensure_wallet(buyer), ensure_wallet(vendedor), get_system_wallet()

    def operar() -> tuple[int, dict[str, Any]]:
        _travar_jogadores(buyer.pk, vendedor.pk)
        anuncio = MarketListing.objects.select_for_update().filter(pk=listing_id).first()
        if anuncio is None:
            raise ListingNotFound
        if anuncio.status != ListingStatus.ACTIVE:
            raise ListingNotActive
        instancia = SkinInstance.objects.select_for_update().filter(pk=anuncio.instance_id).first()
        if instancia is None or instancia.owner_id != vendedor.pk or instancia.consumed_at:
            raise ListingUnavailable
        try:
            para_vendedor, taxa = rules.split_price(anuncio.price)
        except ValueError as erro:  # preço fora do limite, gravado direto no banco
            raise ListingUnavailable from erro
        try:
            inventory_services.change_owner(
                instancia.pk, from_owner=vendedor, to_owner=buyer, authorized_by=anuncio.pk
            )
        except inventory_services.InventoryError as erro:
            raise ListingUnavailable from erro
        linhas = [
            Entry(origem.id, -anuncio.price, kind=_LEDGER_COMPRA),
            Entry(destino.id, para_vendedor, kind=_LEDGER_VENDA),
        ]
        if taxa:
            linhas.append(Entry(sistema.id, taxa, kind=_LEDGER_TAXA))
        grupo = post_entries(
            linhas,
            kind=_LEDGER_COMPRA,
            ref_id=anuncio.pk,
            idempotency_key=f"market_buy:{anuncio.pk}",
        )
        anuncio.status = ListingStatus.SOLD
        anuncio.closed_at = timezone.now()
        anuncio.save(update_fields=["status", "closed_at"])
        venda = MarketTransaction.objects.create(
            listing=anuncio,
            buyer=buyer,
            seller=vendedor,
            price=anuncio.price,
            fee=taxa,
            ledger_group_id=grupo,
        )
        return 201, {
            "id": str(venda.pk),
            "listing_id": str(anuncio.pk),
            "price": venda.price,
            "fee": venda.fee,
            "ledger_group_id": str(grupo),
        }

    try:
        saida = run_once(scope=f"user:{buyer.pk}", key=chave, request_hash=pedido, operation=operar)
    except EconomyInsufficientFunds as erro:
        raise InsufficientFunds from erro
    except EconomyKeyReused as erro:
        raise IdempotencyKeyReused from erro
    corpo = saida.body
    return PurchaseResult(
        id=uuid.UUID(corpo["id"]),
        listing_id=uuid.UUID(corpo["listing_id"]),
        price=corpo["price"],
        fee=corpo["fee"],
        ledger_group_id=uuid.UUID(corpo["ledger_group_id"]),
        replayed=saida.replayed,
    )
