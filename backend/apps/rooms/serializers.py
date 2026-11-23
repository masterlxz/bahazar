from rest_framework import serializers

from .models import Room, RoomInvite, RoomMember


class RoomSerializer(serializers.ModelSerializer):
    """Sala vista por um membro. Só `name` é editável.

    `fields` é explícito (nunca `__all__`): `owner`, `visibility` e `max_members` não podem ser
    alterados pelo corpo da requisição (mass assignment). `role` é o papel de quem pergunta.
    """

    role = serializers.CharField(source="my_role", read_only=True)

    class Meta:
        model = Room
        fields = ("id", "name", "visibility", "max_members", "role", "created_at")
        read_only_fields = ("id", "visibility", "max_members", "created_at")


class MemberSerializer(serializers.ModelSerializer):
    """Um membro como os outros membros o veem. Sem e-mail e sem id: só o que o grupo precisa."""

    username = serializers.CharField(source="user.username", read_only=True)
    avatar = serializers.CharField(source="user.avatar", read_only=True)

    class Meta:
        model = RoomMember
        fields = ("username", "avatar", "role", "joined_at")
        read_only_fields = fields


class InviteSerializer(serializers.ModelSerializer):
    """Um convite para o administrador. Sem `code`: o código só existe na resposta da criação."""

    class Meta:
        model = RoomInvite
        fields = ("id", "expires_at", "max_uses", "uses", "revoked_at", "created_at")
        read_only_fields = fields
