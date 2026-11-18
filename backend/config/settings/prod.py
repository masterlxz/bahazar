"""Produção. Recusa subir sem segredo e sem hosts permitidos (falha rápida e alto)."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


def _obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise ImproperlyConfigured(f"Variável de ambiente obrigatória ausente: {nome}")
    return valor


DEBUG = False
SECRET_KEY = _obrigatoria("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [h.strip() for h in _obrigatoria("DJANGO_ALLOWED_HOSTS").split(",") if h.strip()]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Atrás de proxy TLS (PaaS): confiar no cabeçalho do proxy. Ajustar quando D2 for decidida.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
