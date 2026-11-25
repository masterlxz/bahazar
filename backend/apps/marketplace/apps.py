from django.apps import AppConfig


class MarketplaceConfig(AppConfig):
    name = "apps.marketplace"

    def ready(self) -> None:
        # Importa aqui: o registro de apps precisa estar pronto antes de tocar nos modelos.
        from apps.inventory.services import register_move_guard

        from .guards import listing_guard

        register_move_guard(listing_guard)
