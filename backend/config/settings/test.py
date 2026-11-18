"""Testes (CI). Banco vem das variáveis DB_* do ambiente."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-only-nao-usar-em-producao"  # noqa: S105
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # só para acelerar testes
