from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.trades.expiry import MAX_DAYS, expire_offers

DEFAULT_DAYS = 7  # hipótese do dono (2026-11-27), sem fonte


class Command(BaseCommand):
    help = (
        f"Expira as ofertas de troca pendentes com mais de N dias (padrão {DEFAULT_DAYS}) e solta "
        "os itens delas. GRAVA DADO: use --dry-run antes. Manual: nenhum agendamento chama este "
        "comando."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_DAYS,
            help=f"Prazo em dias, inteiro de 1 a {MAX_DAYS} (padrão: %(default)s).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só informa quantas ofertas expirariam; não altera nada.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days: int = options["days"]
        dry_run: bool = options["dry_run"]
        if not 1 <= days <= MAX_DAYS:
            raise CommandError(f"--days deve estar entre 1 e {MAX_DAYS} (recebi {days}).")

        total = expire_offers(days=days, dry_run=dry_run)
        if dry_run:
            self.stdout.write(
                f"Dry-run: {total} oferta(s) pendente(s) com mais de {days} dia(s) seriam "
                "expiradas. Nada foi alterado."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Expiradas {total} oferta(s) pendente(s) com mais de {days} dia(s)."
                )
            )
