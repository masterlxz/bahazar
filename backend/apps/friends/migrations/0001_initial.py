import uuid

import django.db.models.deletion
import django.db.models.functions.comparison
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Friendship",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendente"),
                            ("accepted", "Aceita"),
                            ("blocked", "Bloqueada"),
                        ],
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "addressee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="friendships_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="friendships_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="friendship",
            index=models.Index(
                fields=["addressee", "status"], name="friendship_addressee_status_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="friendship",
            constraint=models.CheckConstraint(
                condition=models.Q(("requester", models.F("addressee")), _negated=True),
                name="friendship_no_self",
            ),
        ),
        migrations.AddConstraint(
            model_name="friendship",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["pending", "accepted", "blocked"])),
                name="friendship_status_valid",
            ),
        ),
    ]
