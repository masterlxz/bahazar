import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RoomInvite",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("code_hash", models.BinaryField(max_length=32)),
                ("expires_at", models.DateTimeField()),
                ("max_uses", models.PositiveSmallIntegerField()),
                ("uses", models.PositiveSmallIntegerField(default=0)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="room_invites_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="rooms.room",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="roominvite",
            index=models.Index(fields=["room", "revoked_at"], name="room_invite_room_revoked_idx"),
        ),
        migrations.AddConstraint(
            model_name="roominvite",
            constraint=models.CheckConstraint(
                condition=models.Q(("uses__gte", 0)), name="room_invite_uses_nonneg"
            ),
        ),
        migrations.AddConstraint(
            model_name="roominvite",
            constraint=models.CheckConstraint(
                condition=models.Q(("uses__lte", models.F("max_uses"))),
                name="room_invite_uses_within_max",
            ),
        ),
        migrations.AddConstraint(
            model_name="roominvite",
            constraint=models.CheckConstraint(
                condition=models.Q(("max_uses__gte", 1)), name="room_invite_max_uses_min"
            ),
        ),
    ]
