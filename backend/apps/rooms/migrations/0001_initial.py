import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Room",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=60)),
                (
                    "visibility",
                    models.CharField(
                        choices=[("private", "Privada"), ("public", "Pública")],
                        default="private",
                        max_length=10,
                    ),
                ),
                ("max_members", models.PositiveSmallIntegerField(default=20)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_rooms",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RoomMember",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("owner", "Dono"), ("admin", "Administrador"), ("member", "Membro")],
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Ativo"), ("left", "Saiu"), ("banned", "Banido")],
                        max_length=10,
                    ),
                ),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="rooms.room",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="room_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="room",
            constraint=models.CheckConstraint(
                condition=models.Q(("visibility__in", ["private", "public"])),
                name="room_visibility_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="room",
            constraint=models.CheckConstraint(
                condition=models.Q(("max_members__gte", 1)), name="room_max_members_min"
            ),
        ),
        migrations.AddIndex(
            model_name="roommember",
            index=models.Index(fields=["user", "room"], name="room_member_user_room_idx"),
        ),
        migrations.AddConstraint(
            model_name="roommember",
            constraint=models.UniqueConstraint(
                fields=("room", "user"), name="room_member_unique_user"
            ),
        ),
        migrations.AddConstraint(
            model_name="roommember",
            constraint=models.UniqueConstraint(
                condition=models.Q(("role", "owner"), ("status", "active")),
                fields=("room",),
                name="room_member_one_active_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="roommember",
            constraint=models.CheckConstraint(
                condition=models.Q(("role__in", ["owner", "admin", "member"])),
                name="room_member_role_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="roommember",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["active", "left", "banned"])),
                name="room_member_status_valid",
            ),
        ),
    ]
