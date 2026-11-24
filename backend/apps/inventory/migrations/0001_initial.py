import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SkinInstance",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("float_value", models.DecimalField(decimal_places=9, max_digits=10)),
                (
                    "acquired_via",
                    models.CharField(
                        choices=[("admin_grant", "Concedida pelo administrador")], max_length=20
                    ),
                ),
                ("acquired_at", models.DateTimeField(auto_now_add=True)),
                ("acquired_ref_id", models.UUIDField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="skin_instances",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "skin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="instances",
                        to="catalog.skin",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="skininstance",
            index=models.Index(
                condition=models.Q(("consumed_at__isnull", True)),
                fields=["owner"],
                name="skininstance_owner_active_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="skininstance",
            constraint=models.CheckConstraint(
                condition=models.Q(("float_value__gte", 0), ("float_value__lte", 1)),
                name="skininstance_float_unit_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="skininstance",
            constraint=models.CheckConstraint(
                condition=models.Q(("acquired_via__in", ["admin_grant"])),
                name="skininstance_acquired_via_valid",
            ),
        ),
    ]
