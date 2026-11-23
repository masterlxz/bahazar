from rest_framework import serializers

from apps.accounts.models import User

from .models import Friendship


class FriendSerializer(serializers.ModelSerializer):
    """Perfil mínimo de outro jogador. Sem e-mail e sem id: só o que um amigo precisa ver."""

    class Meta:
        model = User
        fields = ("username", "avatar")
        read_only_fields = fields


class FriendshipSerializer(serializers.ModelSerializer):
    """Um pedido, com os dois lados por nome de usuário."""

    requester = serializers.CharField(source="requester.username", read_only=True)
    addressee = serializers.CharField(source="addressee.username", read_only=True)

    class Meta:
        model = Friendship
        fields = ("id", "requester", "addressee", "status", "created_at")
        read_only_fields = fields
