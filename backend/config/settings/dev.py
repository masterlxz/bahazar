"""Desenvolvimento local. A chave abaixo é descartável e NUNCA vale em produção."""

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "dev-only-nao-usar-em-producao"  # noqa: S105
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
