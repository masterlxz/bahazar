import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .avatars import AVATAR_CHOICES, DEFAULT_AVATAR

# Formato único do nome de usuário: minúsculas, números e "_", de 3 a 20 caracteres.
# O mesmo padrão vale na validação (allauth/DRF) e no CHECK do banco.
USERNAME_REGEX = r"^[a-z0-9_]{3,20}$"


class User(AbstractUser):
    """Conta do jogador. UUID como chave primária (decisão tomada antes da 1ª migração)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=20,
        unique=True,
        validators=[
            RegexValidator(
                USERNAME_REGEX,
                "Use de 3 a 20 caracteres: letras minúsculas, números e _.",
            )
        ],
        error_messages={"unique": "Já existe um jogador com esse nome de usuário."},
    )
    avatar = models.CharField(max_length=20, choices=AVATAR_CHOICES, default=DEFAULT_AVATAR)

    class Meta(AbstractUser.Meta):
        constraints = [
            # O banco é a última defesa: mesmo um INSERT direto não burla o formato.
            models.CheckConstraint(
                condition=Q(username__regex=USERNAME_REGEX),
                name="user_username_format",
            ),
            # E-mail único sem distinguir maiúsculas (vazio é permitido: `blank=True` do Django).
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="user_email_unique_ci",
            ),
        ]
