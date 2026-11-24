from django.db import migrations


class Migration(migrations.Migration):
    """O nome antigo (31 caracteres) passa de 30 e o Django recusa no `migrate` (models.E034).

    Renomear por migração nova, e não editar a 0001, vale para qualquer banco: o que já aplicou a
    0001 só renomeia o índice; o banco novo cria e renomeia.
    """

    dependencies = [
        ("friends", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="friendship",
            new_name="friendship_addr_status_idx",
            old_name="friendship_addressee_status_idx",
        ),
    ]
