"""Casca transacional das trocas de itens: trava, revalida, troca os donos e grava o estado.

Ordem global de trava: os DOIS jogadores por id (a mesma de `friends.services`, que trava o par
antes de pedir, aceitar, bloquear ou remover), depois a oferta, depois as instâncias por UUID.
Criar e aceitar seguem essa ordem inteira; recusar e cancelar só travam a oferta. Operações que
seguem uma ordem global única não formam ciclo de espera entre si; isso vale também para as FKs
dos inserts, que tomam KEY SHARE em linhas que a transação já travou. A posse do item só muda em
`inventory.services.change_owner`.
"""

import re
import uuid
from collections.abc import Sequence

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.friends import selectors as friends_selectors
from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance

from . import rules, selectors
from .models import TradeOffer, TradeOfferItem, TradeSide, TradeStatus

# Nome do índice único parcial: é ele que fecha a corrida de duas ofertas com a mesma instância.
_ONE_ACTIVE_PER_INSTANCE = "tradeitem_one_active_per_instance"


class TradeError(Exception):
    """Erro de regra de negócio. `code` é estável: o frontend o traduz."""

    code = "trade_error"
    message = "Operação não permitida."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class SelfTrade(TradeError):
    code = "self_trade"
    message = "Não dá para trocar itens consigo mesmo."


class EmptySide(TradeError):
    code = "empty_side"
    message = "Cada lado da troca precisa de pelo menos um item."


class DuplicateItem(TradeError):
    code = "duplicate_item"
    message = "O mesmo item aparece mais de uma vez na troca."


class InvalidItemId(TradeError):
    code = "invalid_item_id"
    message = "O identificador de um item é inválido."


class TooManyItems(TradeError):
    code = "too_many_items"
    message = "Há itens demais em um dos lados da troca."


class TooManyPendingOffers(TradeError):
    code = "too_many_pending_offers"
    message = "Você já tem trocas pendentes demais."


class NotFriends(TradeError):
    code = "not_friends"
    message = "A troca só é possível entre amigos."


class ItemNotOwned(TradeError):
    code = "item_not_owned"
    message = "Um dos itens não pertence a quem deveria."


class ItemConsumed(TradeError):
    code = "item_consumed"
    message = "Um dos itens já saiu do jogo."


class ItemAlreadyOffered(TradeError):
    code = "item_already_offered"
    message = "Um dos itens já está em outra troca pendente."


class OfferNotFound(TradeError):
    """A oferta não existe ou o chamador não faz parte dela: a view responde 404."""

    code = "offer_not_found"
    message = "Não encontrado."


class NotAllowed(TradeError):
    code = "not_allowed"
    message = "Você não pode fazer isto nesta troca."


class OfferNotPending(TradeError):
    code = "offer_not_pending"
    message = "Esta troca já foi resolvida."


_CONSTRAINT_NO_TEXTO = re.compile(r'constraint "([^"]+)"')


def violated_constraint(erro: IntegrityError) -> str | None:
    """O nome da constraint que o banco acusou, ou `None` se não der para saber.

    Lê do `diag` do driver (`constraint_name`), que não depende do idioma nem do formato da
    mensagem. Sem `diag`, cai para o texto da mensagem, que cita `constraint "nome"`.
    """
    diag = getattr(erro.__cause__, "diag", None)
    nome = getattr(diag, "constraint_name", None)
    if nome:
        return str(nome)
    achado = _CONSTRAINT_NO_TEXTO.search(str(erro))
    return achado.group(1) if achado else None


_FALHAS_DA_FORMA: dict[str, type[TradeError]] = {
    rules.SELF_TRADE: SelfTrade,
    rules.EMPTY_SIDE: EmptySide,
    rules.INVALID_ID: InvalidItemId,
    rules.TOO_MANY_ITEMS: TooManyItems,
    rules.DUPLICATE_ITEM: DuplicateItem,
}

_FALHAS_DO_ITEM: dict[str, type[TradeError]] = {
    rules.NOT_OWNER: ItemNotOwned,
    rules.CONSUMED: ItemConsumed,
}


def _conferir_itens(
    instancias: dict[uuid.UUID, SkinInstance],
    itens: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Cada `(instance_id, dono_esperado)` tem de estar com o dono certo e em jogo.

    Um id que não existe conta como "não é do dono": quem pede não descobre quais ids existem.
    """
    for instance_id, dono_esperado in itens:
        instancia = instancias.get(instance_id)
        problema = rules.item_problem(
            expected_owner_id=dono_esperado,
            actual_owner_id=instancia.owner_id if instancia else None,
            consumed=instancia is not None and instancia.consumed_at is not None,
        )
        if problema is not None:
            raise _FALHAS_DO_ITEM[problema]


def create_offer(
    proposer: User,
    recipient: User,
    offered_ids: Sequence[uuid.UUID],
    requested_ids: Sequence[uuid.UUID],
) -> TradeOffer:
    """O proponente oferece itens seus e pede itens do destinatário (só entre amigos aceitos).

    Segue a mesma ordem de trava do aceite: os dois jogadores por id, depois as instâncias por
    UUID. Amizade, teto de pendentes, dono, consumo e ocupação são conferidos SOB essa trava,
    antes de gravar: lendo antes dela, uma troca de dono no meio deixaria uma oferta obsoleta.
    O índice único parcial do banco continua como rede de segurança (e é ele quem recusa se uma
    checagem em Python deixar passar); o `IntegrityError` dele vira `ItemAlreadyOffered`.
    """
    problema = rules.offer_shape_problem(proposer.pk, recipient.pk, offered_ids, requested_ids)
    if problema is not None:
        raise _FALHAS_DA_FORMA[problema]
    todos = [*offered_ids, *requested_ids]
    esperados = [(i, proposer.pk) for i in offered_ids]
    esperados += [(i, recipient.pk) for i in requested_ids]
    try:
        with transaction.atomic():
            if not friends_selectors.can_view(proposer, recipient):
                raise NotFriends
            if rules.pending_limit_exceeded(selectors.pending_count(proposer)):
                raise TooManyPendingOffers
            travadas = SkinInstance.objects.select_for_update().filter(pk__in=todos)
            instancias = {i.pk: i for i in travadas.order_by("pk")}
            _conferir_itens(instancias, esperados)
            if selectors.busy_instance_ids(todos):
                raise ItemAlreadyOffered
            lados = dict.fromkeys(offered_ids, TradeSide.OFFERED)
            lados.update(dict.fromkeys(requested_ids, TradeSide.REQUESTED))
            oferta = TradeOffer.objects.create(proposer=proposer, recipient=recipient)
            for instance_id in sorted(lados):
                TradeOfferItem.objects.create(
                    offer=oferta, instance_id=instance_id, side=lados[instance_id]
                )
    except IntegrityError as erro:
        if violated_constraint(erro) != _ONE_ACTIVE_PER_INSTANCE:
            raise
        raise ItemAlreadyOffered from erro
    return oferta


def _dono_declarado(oferta: TradeOffer, item: TradeOfferItem) -> uuid.UUID:
    """O dono esperado: o proponente no lado oferecido, o destinatário no lado pedido."""
    return oferta.proposer_id if item.side == TradeSide.OFFERED else oferta.recipient_id


def _travar_jogadores(*ids: uuid.UUID) -> None:
    """Trava as linhas dos jogadores em ordem de id, a mesma de `friends.services`.

    Assim, criar ou aceitar uma troca e uma operação de `friends.services` sobre o mesmo par
    (que também trava por id) nunca esperam em ordem oposta. Sem o `order_by`, o Postgres trava
    na ordem em que lê, que não é a de id.
    """
    list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def _oferta_para(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    """A oferta (sem trava) se `actor` faz parte dela; senão, `OfferNotFound`."""
    oferta = selectors.offer_for_party(actor, offer_id)
    if oferta is None:
        raise OfferNotFound
    return oferta


def _travar_oferta(actor: User, offer_id: uuid.UUID, acao: str) -> TradeOffer:
    """Trava a oferta e confere, JÁ sob a trava, quem pode agir e se ainda está pendente."""
    oferta = TradeOffer.objects.select_for_update().get(pk=offer_id)
    pode = rules.may_act(
        acao, actor_id=actor.pk, proposer_id=oferta.proposer_id, recipient_id=oferta.recipient_id
    )
    if not pode:
        raise NotAllowed
    if not rules.can_resolve(oferta.status):
        raise OfferNotPending
    return oferta


def _encerrar(oferta: TradeOffer, acao: str) -> TradeOffer:
    """Grava o estado terminal e libera as instâncias (`active=False`) na mesma transação."""
    oferta.status = TradeStatus(rules.status_after(acao))
    oferta.resolved_at = timezone.now()
    oferta.save(update_fields=["status", "resolved_at"])
    TradeOfferItem.objects.filter(offer=oferta).update(active=False)
    return oferta


def accept_offer(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    """O destinatário aceita: tudo é revalidado sob trava e os donos trocam, ou nada muda."""
    previa = _oferta_para(actor, offer_id)
    with transaction.atomic():
        _travar_jogadores(previa.proposer_id, previa.recipient_id)
        oferta = _travar_oferta(actor, offer_id, rules.ACCEPT)
        if not friends_selectors.can_view(previa.proposer, previa.recipient):
            raise NotFriends
        itens = list(oferta.items.all())
        ids = sorted(i.instance_id for i in itens)
        instancias = {
            i.pk: i
            for i in SkinInstance.objects.select_for_update().filter(pk__in=ids).order_by("pk")
        }
        _conferir_itens(instancias, [(i.instance_id, _dono_declarado(oferta, i)) for i in itens])
        for item in sorted(itens, key=lambda i: i.instance_id):
            if item.side == TradeSide.OFFERED:
                de, para = previa.proposer, previa.recipient
            else:
                de, para = previa.recipient, previa.proposer
            inventory_services.change_owner(item.instance_id, from_owner=de, to_owner=para)
        return _encerrar(oferta, rules.ACCEPT)


def _resolver_sem_troca(actor: User, offer_id: uuid.UUID, acao: str) -> TradeOffer:
    _oferta_para(actor, offer_id)
    with transaction.atomic():
        return _encerrar(_travar_oferta(actor, offer_id, acao), acao)


def decline_offer(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    """O destinatário recusa: nada muda de dono e as instâncias ficam livres."""
    return _resolver_sem_troca(actor, offer_id, rules.DECLINE)


def cancel_offer(actor: User, offer_id: uuid.UUID) -> TradeOffer:
    """O proponente cancela: nada muda de dono e as instâncias ficam livres."""
    return _resolver_sem_troca(actor, offer_id, rules.CANCEL)
