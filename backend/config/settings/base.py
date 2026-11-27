"""Configuração comum a todos os ambientes. Nada aqui contém segredo."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "apps.core",
    "apps.accounts",
    "apps.rooms",
    "apps.economy",
    "apps.friends",
    "apps.catalog",
    "apps.inventory",
    "apps.trades",
    "apps.marketplace",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "bahazar"),
        "USER": os.environ.get("DB_USER", "bahazar"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Autenticação (ADR 0008; SEGURANCA §4) ---------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Sessão por cookie HttpOnly (JavaScript não lê) + CSRF. O cookie de CSRF, ao contrário, precisa
# ser legível pelo frontend para ele devolver o token no cabeçalho `X-CSRFToken`.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 dias
CSRF_COOKIE_HTTPONLY = False

# allauth, modo headless (só API JSON, cliente "browser"). Sem telas HTML do allauth.
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*"]
# "optional" por enquanto (ainda não há provedor de e-mail); passa a "mandatory" antes do deploy.
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_PRESERVE_USERNAME_CASING = False  # grava em minúsculas
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_USERNAME_BLACKLIST = [
    "admin",
    "administrator",
    "root",
    "system",
    "sistema",
    "support",
    "suporte",
    "staff",
    "moderator",
    "mod",
    "bahazar",
    "api",
    "null",
]
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": FRONTEND_URL + "/account/verify-email/{key}",
    "account_reset_password": FRONTEND_URL + "/account/password/reset",
    "account_reset_password_from_key": FRONTEND_URL + "/account/password/reset/key/{key}",
    "account_signup": FRONTEND_URL + "/account/signup",
}

# Negar por omissão (SEGURANCA §3): toda view exige autenticação, salvo declaração explícita.
# Só sessão (com CSRF): nada de BasicAuthentication nem token em cabeçalho.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Erros do DRF (JSON quebrado, página inválida, CSRF, 405, 429...) saem como `{code, message}`.
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    # Só vale em view com `throttle_classes = [ScopedRateThrottle]` e `throttle_scope`.
    # O limite mora no cache do Django: em produção, o cache em banco (ver prod.py).
    "DEFAULT_THROTTLE_RATES": {
        "invite_redeem": "10/min",
        "market_listing_create": "30/min",
        "market_listing_cancel": "60/min",
        "market_listing_buy": "30/min",  # hipótese, sem fonte
        "market_listing_read": "120/min",  # lista e detalhe da vitrine; hipótese, sem fonte
        "trade_create": "30/min",  # POST /trades/; hipótese, sem fonte
        "trade_resolve": "60/min",  # accept, decline e cancel dividem o balde; hipótese, sem fonte
    },
}
