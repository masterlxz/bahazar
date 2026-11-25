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
            name="TradeOffer",
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
                            ("declined", "Recusada"),
                            ("cancelled", "Cancelada"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "proposer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trade_offers_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trade_offers_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TradeOfferItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "side",
                    models.CharField(
                        choices=[("offered", "Oferecido"), ("requested", "Pedido")],
                        max_length=10,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "instance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trade_items",
                        to="inventory.skininstance",
                    ),
                ),
                (
                    "offer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="trades.tradeoffer",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="tradeoffer",
            index=models.Index(
                fields=["recipient", "status"], name="tradeoffer_recip_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="tradeoffer",
            index=models.Index(fields=["proposer", "status"], name="tradeoffer_prop_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="tradeoffer",
            constraint=models.CheckConstraint(
                condition=models.Q(("proposer", models.F("recipient")), _negated=True),
                name="tradeoffer_no_self",
            ),
        ),
        migrations.AddConstraint(
            model_name="tradeoffer",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("status__in", ["pending", "accepted", "declined", "cancelled"])
                ),
                name="tradeoffer_status_valid",
            ),
        ),
        # `resolved_at` nulo se, e só se, a oferta está pendente: mesma expressão do modelo.
        migrations.AddConstraint(
            model_name="tradeoffer",
            constraint=models.CheckConstraint(
                condition=models.Q(status="pending", resolved_at__isnull=True)
                | (~models.Q(status="pending") & models.Q(resolved_at__isnull=False)),
                name="tradeoffer_resolved_matches_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="tradeofferitem",
            constraint=models.UniqueConstraint(
                fields=("offer", "instance"), name="tradeitem_unique_offer_instance"
            ),
        ),
        migrations.AddConstraint(
            model_name="tradeofferitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(("active", True)),
                fields=("instance",),
                name="tradeitem_one_active_per_instance",
            ),
        ),
        migrations.AddConstraint(
            model_name="tradeofferitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("side__in", ["offered", "requested"])),
                name="tradeitem_side_valid",
            ),
        ),
    ]
