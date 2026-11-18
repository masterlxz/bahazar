from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    """Perfil do próprio jogador. Só o avatar é editável; o resto é somente leitura.

    `fields` é explícito de propósito (nunca `__all__`): campo novo no modelo não vira
    campo da API por acidente (mass assignment).
    """

    class Meta:
        model = User
        fields = ("id", "username", "email", "avatar")
        read_only_fields = ("id", "username", "email")
