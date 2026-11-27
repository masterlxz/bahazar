from django.apps import AppConfig


class TradesConfig(AppConfig):
    name = "apps.trades"

    def ready(self) -> None:
        # Importa aqui: o registro de apps precisa estar pronto antes de tocar nos modelos.
        from apps.friends.hooks import register_pair_ended_hook
        from apps.inventory.services import register_move_guard

        from .guards import offer_guard
        from .services import cancel_pending_between

        register_move_guard(offer_guard)
        # Bloquear ou desfazer a amizade cancela as ofertas pendentes do par, na mesma transação.
        register_pair_ended_hook(cancel_pending_between)
