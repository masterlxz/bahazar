"""Regras transacionais dos anúncios: criar e cancelar, sempre sob trava."""

import re
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance

from . import selectors
from .models import ListingStatus, MarketListing

_ONE_ACTIVE_PER_INSTANCE = "marketlist_one_active_instance"


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


def create_listing(seller: User, instance_id: uuid.UUID, price: int) -> MarketListing:
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


def cancel_listing(user: User, listing_id: uuid.UUID) -> MarketListing:
    """Cancela um anúncio ativo do vendedor.

    A linha do anúncio é travada antes de conferir dono e estado. Um anúncio de outra pessoa e
    um anúncio inexistente dão o mesmo 404; um anúncio já fechado dá 409.
    """
    with transaction.atomic():
        anuncio = MarketListing.objects.filter(pk=listing_id).first()
        if anuncio is None or anuncio.seller_id != user.pk:
            raise ListingNotFound
        if anuncio.status != ListingStatus.ACTIVE:
            raise ListingNotActive
        anuncio.status = ListingStatus.CANCELLED
        anuncio.closed_at = timezone.now()
        anuncio.save(update_fields=["status", "closed_at"])
        return anuncio
