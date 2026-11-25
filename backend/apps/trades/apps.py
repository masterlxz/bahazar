from django.apps import AppConfig


class TradesConfig(AppConfig):
    name = "apps.trades"

    def ready(self) -> None:
        # Importa aqui: o registro de apps precisa estar pronto antes de tocar nos modelos.
        from apps.inventory.services import register_move_guard

        from .guards import offer_guard

        _ = (register_move_guard, offer_guard)
