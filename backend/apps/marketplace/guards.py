"""Guarda do mercado sobre a posse de itens: item anunciado não muda de dono."""

import uuid

from apps.inventory.models import SkinInstance
from apps.inventory.services import ItemLocked

from .models import ListingStatus, MarketListing


def listing_guard(instance: SkinInstance, authorized_by: uuid.UUID | None) -> None:
    """Recusa se a instância tem um anúncio ativo que não é a `authorized_by`.

    `authorized_by` é o id do anúncio que o chamador está executando. É um crachá de servidor,
    não uma capacidade verificada: só código de servidor que já executa a operação dona da
    trava o passa. Nunca preencha esse valor com dado vindo de uma requisição.

    A guarda é só um SELECT, sem `select_for_update`, como exige o contrato de
    `inventory.services.register_move_guard`.
    """
    anuncios = MarketListing.objects.filter(
        instance_id=instance.pk,
        status=ListingStatus.ACTIVE,
    )
    if authorized_by is not None:
        anuncios = anuncios.exclude(pk=authorized_by)
    if anuncios.exists():
        raise ItemLocked
