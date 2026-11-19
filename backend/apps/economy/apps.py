from django.apps import AppConfig


class EconomyConfig(AppConfig):
    name = "apps.economy"

    def ready(self) -> None:
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from . import signals

        # A economia escuta o `accounts` (nunca o contrário): todo usuário novo ganha carteira.
        post_save.connect(
            signals.abrir_carteira_do_novo_usuario,
            sender=get_user_model(),
            dispatch_uid="economy_open_wallet",
        )
