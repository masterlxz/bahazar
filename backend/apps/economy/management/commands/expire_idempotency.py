from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.economy.idempotency_expiry import MAX_DAYS, expire_records

DEFAULT_DAYS = 7


class Command(BaseCommand):
    help = (
        f"Apaga os registros de idempotência com mais de N dias (padrão {DEFAULT_DAYS}). "
        "APAGA DADO: use --dry-run antes. Manual: nenhum agendamento chama este comando."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_DAYS,
            help=f"Retenção em dias, inteiro de 1 a {MAX_DAYS} (padrão: %(default)s).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só informa quantos registros seriam apagados; não apaga nada.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days: int = options["days"]
        dry_run: bool = options["dry_run"]
        if not 1 <= days <= MAX_DAYS:
            raise CommandError(f"--days deve estar entre 1 e {MAX_DAYS} (recebi {days}).")

        total = expire_records(days=days, dry_run=dry_run)
        if dry_run:
            self.stdout.write(
                f"Dry-run: {total} registro(s) de idempotência com mais de {days} dia(s) "
                "seriam apagados. Nada foi apagado."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Apagados {total} registro(s) de idempotência com mais de {days} dia(s)."
                )
            )
