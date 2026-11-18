"""Configuração de autenticação: o que NÃO pode ser afrouxado sem um teste falhar."""

from django.conf import settings


def test_drf_so_aceita_sessao_com_csrf() -> None:
    # Sem BasicAuthentication nem token em cabeçalho: só o cookie de sessão (que passa por CSRF).
    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "rest_framework.authentication.SessionAuthentication"
    ]


def test_cookie_de_sessao_nao_e_legivel_por_javascript() -> None:
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"


def test_senha_exige_pelo_menos_10_caracteres() -> None:
    minimo = [
        v["OPTIONS"]["min_length"]
        for v in settings.AUTH_PASSWORD_VALIDATORS
        if v["NAME"].endswith("MinimumLengthValidator")
    ]

    assert minimo == [10]


def test_login_aceita_usuario_ou_email() -> None:
    assert set(settings.ACCOUNT_LOGIN_METHODS) == {"username", "email"}


def test_verificacao_de_email_opcional_por_enquanto() -> None:
    # Muda para "mandatory" antes do deploy (D2): ver project/PENDING.md.
    assert settings.ACCOUNT_EMAIL_VERIFICATION == "optional"
