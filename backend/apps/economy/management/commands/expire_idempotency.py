"""STUB do commit só-de-teste: aceita os argumentos e não faz nada."""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "STUB"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        return None
