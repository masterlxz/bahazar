from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.economy.audit import check_ledger


class Command(BaseCommand):
    help = "Confere as invariantes do ledger (soma zero e saldo = extrato). Sai com erro se falhar."

    def handle(self, *args: Any, **options: Any) -> None:
        problemas = check_ledger()
        if problemas:
            raise CommandError("Ledger inconsistente:\n" + "\n".join(problemas))
        self.stdout.write(self.style.SUCCESS("Ledger íntegro."))
