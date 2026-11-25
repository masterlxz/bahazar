import os
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.catalog.importer import CatalogImportError, import_catalog, import_catalog_from_api

MAX_NAMES_SHOWN = 20
SKINPORT_ITEMS_URL = "https://api.skinport.com/v1/items"


class Command(BaseCommand):
    help = (
        "Importa o catálogo de skins e preços de referência.\n"
        "Modo arquivo (padrão): --catalog skins.json --prices skinport.json\n"
        "Modo API: --fetch --catalog skins.json [--app-id 730 --currency USD]"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--catalog", required=True, help="skins.json do catálogo (ByMykel)")
        parser.add_argument("--prices", help="JSON de preços da Skinport (modo arquivo)")
        parser.add_argument(
            "--fetch",
            action="store_true",
            help="Baixar preços da API da Skinport em vez de arquivo",
        )
        parser.add_argument(
            "--app-id", type=int, default=730, help="App ID do jogo (padrão 730=CS2)"
        )
        parser.add_argument("--currency", default="USD", help="Moeda dos preços (padrão USD)")

    def handle(self, *args: Any, **options: Any) -> None:
        catalog_path = Path(options["catalog"])
        fetch = options["fetch"]

        if fetch:
            prices_path = options["prices"]
            if prices_path:
                raise CommandError("--prices não deve ser usado com --fetch")
            app_id = options["app_id"]
            currency = options["currency"]
            client_id = os.environ.get("SKINPORT_CLIENT_ID")
            client_secret = os.environ.get("SKINPORT_CLIENT_SECRET")
            if client_id and client_secret:
                self.stdout.write("Usando API key Skinport (limite próprio)")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "Sem SKINPORT_CLIENT_ID/SKINPORT_CLIENT_SECRET; "
                        "usando IP compartilhado (limite /24)"
                    )
                )
            try:
                r = import_catalog_from_api(
                    catalog_path=catalog_path,
                    app_id=app_id,
                    currency=currency,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            except CatalogImportError as erro:
                raise CommandError(str(erro)) from erro
        else:
            prices_path = options["prices"]
            if not prices_path:
                raise CommandError("--prices é obrigatório sem --fetch")
            try:
                r = import_catalog(catalog_path, Path(prices_path))
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
