"""Desenvolvimento local. A chave abaixo é descartável e NUNCA vale em produção."""

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "dev-only-nao-usar-em-producao"  # noqa: S105
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Sem provedor de e-mail ainda: os e-mails (confirmação, redefinição) saem no console do servidor.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
