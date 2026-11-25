"""Guarda de `trades` sobre a posse de itens (I-6): item em oferta pendente não muda de dono.

O núcleo `inventory` não conhece `trades`: `apps.py` registra esta função em
`inventory.services.register_move_guard`, e `change_owner` a chama, sob a trava da instância.
Sem ela, um módulo que movesse o item por outro caminho (mercado, trade-up) deixaria a oferta
pendente presa, e o índice `tradeitem_one_active_per_instance` impediria o novo dono de
oferecê-lo.
"""

import uuid

from apps.inventory.models import SkinInstance
from apps.inventory.services import ItemLocked

from .models import TradeOfferItem


def offer_guard(instancia: SkinInstance, authorized_by: uuid.UUID | None) -> None:
    """Recusa se a instância está numa oferta pendente que não é a `authorized_by`.

    `authorized_by` é o id da oferta que o chamador está executando (o aceite move os itens da
    própria oferta). Só conta item `active=True`, ou seja, de oferta ainda pendente; vale para o
    lado oferecido e para o pedido, como o índice único do banco.
    """
    em_oferta = TradeOfferItem.objects.filter(instance_id=instancia.pk, active=True)
    if authorized_by is not None:
        em_oferta = em_oferta.exclude(offer_id=authorized_by)
    if em_oferta.exists():
        raise ItemLocked
