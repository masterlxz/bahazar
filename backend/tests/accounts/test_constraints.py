"""Garantias no BANCO: valem mesmo se um bug de aplicação (ou um INSERT direto) tentar burlar."""

import uuid

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import DataError, IntegrityError, transaction

from .conftest import SENHA_FORTE, User, criar_usuario

pytestmark = pytest.mark.django_db


def test_usuario_usa_uuid_como_chave_primaria() -> None:
    usuario = criar_usuario()

    assert isinstance(usuario.pk, uuid.UUID)
    assert settings.AUTH_USER_MODEL == "accounts.User"


@pytest.mark.parametrize("username", ["ab", "x" * 21, "A!", "Ana_01", "com espaco", "a-b"])
def test_banco_recusa_username_fora_do_padrao(username: str) -> None:
    # 21 caracteres estoura o varchar(20) (DataError); os demais violam o CHECK (IntegrityError).
    with pytest.raises((IntegrityError, DataError)), transaction.atomic():
        User.objects.create_user(username=username, email="x@exemplo.com", password=SENHA_FORTE)


def test_banco_recusa_email_duplicado_sem_distinguir_maiusculas() -> None:
    criar_usuario(username="ana_01", email="ana@exemplo.com")

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(username="bia_02", email="ANA@exemplo.com", password=SENHA_FORTE)


def test_nao_ha_migracao_pendente() -> None:
    # Falha se alguém mudar um model e esquecer de gerar a migração.
    call_command("makemigrations", "--check", "--dry-run", verbosity=3)
