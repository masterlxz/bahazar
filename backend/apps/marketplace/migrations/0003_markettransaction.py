import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Imutabilidade das vendas (MODELO-DE-DADOS §4.3): o trigger barra UPDATE e DELETE até para
# superusuário; correção de erro é lançamento compensatório no ledger, nunca edição da venda.
# Mesmo desenho de `economy/migrations/0002`. Não há trigger de TRUNCATE (o `flush` dos testes de
# concorrência usa TRUNCATE); o REVOKE com dois papéis de banco fica para o deploy (PENDING).
# As instruções vão em tupla para o Django não precisar dividir o texto com `$$`.
CRIAR = (
    """
    CREATE FUNCTION marketplace_markettransaction_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'marketplace_markettransaction é append-only: % bloqueado', TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER marketplace_markettransaction_append_only
    BEFORE UPDATE OR DELETE ON marketplace_markettransaction
    FOR EACH ROW EXECUTE FUNCTION marketplace_markettransaction_append_only()
    """,
)

REMOVER = (
    "DROP TRIGGER marketplace_markettransaction_append_only ON marketplace_markettransaction",
    "DROP FUNCTION marketplace_markettransaction_append_only()",
)


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0002_marketlisting_closed_matches_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketTransaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("price", models.BigIntegerField()),
                ("fee", models.BigIntegerField()),
                ("ledger_group_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "buyer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="market_purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sale",
                        to="marketplace.marketlisting",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="market_sales",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("buyer", models.F("seller")), _negated=True),
                        name="markettx_buyer_not_seller",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("fee__gte", 0), ("fee__lt", models.F("price"))),
                        name="markettx_fee_below_price",
                    ),
                ],
            },
        ),
        migrations.RunSQL(sql=CRIAR, reverse_sql=REMOVER),
    ]
