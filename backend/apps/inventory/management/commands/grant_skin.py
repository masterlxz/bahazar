import secrets
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.models import User
from apps.catalog.models import Skin
from apps.inventory import rules, services


class Command(BaseCommand):
    help = (
        "Dá uma skin a um jogador (uso administrativo, sem API). O float é sorteado dentro da "
        "faixa da skin, ou informado com --float. A skin precisa estar ativa."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--user", required=True, help="nome de usuário do jogador")
        parser.add_argument("--skin", required=True, help="external_id da skin (id do catálogo)")
        parser.add_argument("--float", dest="float_value", help="float exato (0 a 1)")

    def handle(self, *args: Any, **options: Any) -> None:
        owner = User.objects.filter(username=str(options["user"]).strip().lower()).first()
        if owner is None:
            raise CommandError(f"Jogador não encontrado: {options['user']}")
        skin = Skin.objects.filter(external_id=options["skin"]).first()
        if skin is None:
            raise CommandError(f"Skin não encontrada: {options['skin']}")

        if options["float_value"] is None:
            # `secrets` por hábito: aqui o sorteio não é de dinheiro, mas custa o mesmo.
            unit = Decimal(repr(secrets.SystemRandom().random()))
            valor = rules.draw_float(skin.min_float, skin.max_float, unit)
        else:
            try:
                valor = Decimal(options["float_value"])
            except InvalidOperation:
                raise CommandError(f"--float não é um número: {options['float_value']}") from None

        try:
            instancia = services.create_instance(owner, skin, valor, acquired_via="admin_grant")
        except services.InventoryError as erro:
            raise CommandError(str(erro)) from erro

        self.stdout.write(
            self.style.SUCCESS(
                f"Criada {instancia.id}: {skin.name} ({rules.wear_for(instancia.float_value)}, "
                f"float {instancia.float_value}) para {owner.username}."
            )
        )
