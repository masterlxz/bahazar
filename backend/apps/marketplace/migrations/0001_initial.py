import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("inventory", "0002_float_in_skin_range_trigger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketListing",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("price", models.BigIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Ativo"),
                            ("sold", "Vendido"),
                            ("cancelled", "Cancelado"),
                        ],
                        default="active",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "instance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="market_listings",
                        to="inventory.skininstance",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="market_listings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="marketlisting",
            index=models.Index(fields=["seller"], name="marketlisting_seller_idx"),
        ),
        migrations.AddIndex(
            model_name="marketlisting",
            index=models.Index(
                fields=["status", "-created_at"],
                name="marketlist_status_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="marketlisting",
            constraint=models.CheckConstraint(
                condition=models.Q(("price__gte", 0)),
                name="marketlisting_price_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="marketlisting",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["active", "sold", "cancelled"])),
                name="marketlisting_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="marketlisting",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "active")),
                fields=("instance",),
                name="marketlist_one_active_instance",
            ),
        ),
    ]
