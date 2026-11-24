import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Skin",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("weapon", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=200)),
                ("collection", models.CharField(blank=True, max_length=200)),
                ("rarity", models.CharField(max_length=64)),
                ("min_float", models.DecimalField(decimal_places=9, max_digits=10)),
                ("max_float", models.DecimalField(decimal_places=9, max_digits=10)),
                ("reference_price", models.BigIntegerField()),
                ("image_url", models.CharField(blank=True, default="", max_length=500)),
                ("image_source", models.CharField(default="none", max_length=20)),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="skin",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("max_float__lte", 1),
                    ("min_float__gte", 0),
                    ("min_float__lt", models.F("max_float")),
                ),
                name="skin_float_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="skin",
            constraint=models.CheckConstraint(
                condition=models.Q(("reference_price__gt", 0)),
                name="skin_reference_price_positive",
            ),
        ),
    ]
