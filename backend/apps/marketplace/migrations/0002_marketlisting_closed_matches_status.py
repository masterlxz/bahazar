from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0001_initial"),
    ]

    operations = [
        # `closed_at` nulo se, e só se, o anúncio está ativo: mesma expressão do modelo.
        migrations.AddConstraint(
            model_name="marketlisting",
            constraint=models.CheckConstraint(
                condition=models.Q(status="active", closed_at__isnull=True)
                | (~models.Q(status="active") & models.Q(closed_at__isnull=False)),
                name="marketlisting_closed_matches_status",
            ),
        ),
    ]
