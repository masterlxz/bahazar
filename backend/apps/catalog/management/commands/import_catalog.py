from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.catalog.importer import CatalogImportError, import_catalog

MAX_NAMES_SHOWN = 20


class Command(BaseCommand):
    help = (
        "Importa o catálogo de skins e os preços de referência de dois arquivos JSON locais "
        "(catálogo ByMykel e snapshot da Skinport). Tudo ou nada: se algo for inválido, "
        "nada é gravado. Reexecutar com os mesmos arquivos não altera nada."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--catalog", required=True, help="skins.json do catálogo")
        parser.add_argument("--prices", required=True, help="JSON de preços da Skinport")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            r = import_catalog(Path(options["catalog"]), Path(options["prices"]))
        except CatalogImportError as erro:
            raise CommandError(str(erro)) from erro
        for nome in r.no_price[:MAX_NAMES_SHOWN]:
            self.stdout.write(f"sem preço: {nome}")
        if len(r.no_price) > MAX_NAMES_SHOWN:
            self.stdout.write(f"... e mais {len(r.no_price) - MAX_NAMES_SHOWN} sem preço")
        self.stdout.write(
            self.style.SUCCESS(
                f"{r.created} criadas, {r.updated} atualizadas, {r.unchanged} sem mudança, "
                f"{r.deactivated} desativadas, {r.excluded} ignoradas (StatTrak, Souvenir, "
                f"faca), {len(r.no_price)} sem preço."
            )
        )
