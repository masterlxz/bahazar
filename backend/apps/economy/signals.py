from typing import Any

from . import services


def abrir_carteira_do_novo_usuario(
    sender: Any, instance: Any, created: bool, raw: bool = False, **kwargs: Any
) -> None:
    """`raw` é o carregamento de fixtures: nesse caso o ledger não deve ser tocado."""
    if created and not raw:
        services.open_wallet(instance)
