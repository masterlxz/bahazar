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
            name="Wallet",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("player", "Jogador"), ("system", "Sistema")], max_length=10
                    ),
                ),
                ("balance", models.BigIntegerField(default=0)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="wallet",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WalletTransaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("group_id", models.UUIDField()),
                ("amount", models.BigIntegerField()),
                ("balance_after", models.BigIntegerField()),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("starting_grant", "Saldo inicial"),
                            ("daily_reward", "Recompensa diária"),
                            ("ad_reward", "Recompensa por anúncio"),
                            ("transfer", "Transferência"),
                            ("trade", "Troca"),
                            ("market_sale", "Venda no mercado"),
                            ("market_purchase", "Compra no mercado"),
                            ("market_fee", "Taxa do mercado"),
                            ("case_open", "Abertura de caixa"),
                            ("case_reward", "Prêmio de caixa"),
                            ("tradeup", "Trade-up"),
                            ("quest_reward", "Recompensa de missão"),
                            ("adjustment", "Ajuste"),
                        ],
                        max_length=20,
                    ),
                ),
                ("ref_id", models.UUIDField(blank=True, null=True)),
                ("idempotency_key", models.CharField(blank=True, default="", max_length=100)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "wallet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transactions",
                        to="economy.wallet",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DailyClaim",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("claim_number", models.PositiveIntegerField()),
                ("claimed_at", models.DateTimeField()),
                ("streak_day", models.PositiveIntegerField()),
                ("amount", models.BigIntegerField()),
                ("ledger_group_id", models.UUIDField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="daily_claims",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "claim_number"), name="dailyclaim_unique_number"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("streak_day__gte", 1)), name="dailyclaim_streak_gte_1"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", 0)), name="dailyclaim_amount_gt_0"
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ["player", "system"])), name="wallet_kind_valid"
            ),
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind", "system"), ("balance__gte", 0), _connector="OR"),
                name="wallet_player_balance_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("kind", "player"), ("user__isnull", False)),
                    models.Q(("kind", "system"), ("user__isnull", True)),
                    _connector="OR",
                ),
                name="wallet_kind_matches_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", "system")), fields=("kind",), name="wallet_single_system"
            ),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=["wallet", "-created_at", "id"], name="wallettx_extract_idx"),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=["group_id"], name="wallettx_group_idx"),
        ),
        migrations.AddConstraint(
            model_name="wallettransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount", 0), _negated=True), name="wallettx_amount_not_zero"
            ),
        ),
        migrations.AddConstraint(
            model_name="wallettransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "kind__in",
                        [
                            "starting_grant",
                            "daily_reward",
                            "ad_reward",
                            "transfer",
                            "trade",
                            "market_sale",
                            "market_purchase",
                            "market_fee",
                            "case_open",
                            "case_reward",
                            "tradeup",
                            "quest_reward",
                            "adjustment",
                        ],
                    )
                ),
                name="wallettx_kind_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="wallettransaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key", ""), _negated=True),
                fields=("wallet", "idempotency_key"),
                name="wallettx_unique_idempotency_key",
            ),
        ),
    ]
