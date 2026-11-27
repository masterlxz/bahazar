from django.db import migrations, models


class Migration(migrations.Migration):
    """Acrescenta o estado `expired` (expiração das ofertas pendentes, Sessão 49).

    Só troca as `choices` e a CHECK `tradeoffer_status_valid`; nenhum dado muda. A CHECK
    `tradeoffer_resolved_matches_status` não precisa mudar: `expired` já cai em "resolvida, com
    `resolved_at`". Escrita à mão; o `test_nao_ha_migracao_pendente` confere que bate com o modelo.
    """

    dependencies = [
        ("trades", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tradeoffer",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendente"),
                    ("accepted", "Aceita"),
                    ("declined", "Recusada"),
                    ("cancelled", "Cancelada"),
                    ("expired", "Expirada"),
                ],
                default="pending",
                max_length=10,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="tradeoffer",
            name="tradeoffer_status_valid",
        ),
        migrations.AddConstraint(
            model_name="tradeoffer",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("status__in", ["pending", "accepted", "declined", "cancelled", "expired"])
                ),
                name="tradeoffer_status_valid",
            ),
        ),
    ]
