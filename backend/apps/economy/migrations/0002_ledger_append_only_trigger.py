from django.db import migrations

# Imutabilidade do ledger (ADR 0003, MODELO-DE-DADOS §4.3). O trigger barra UPDATE e DELETE
# até para superusuário; correção de erro é lançamento compensatório (`adjustment`).
#
# Não há trigger de TRUNCATE: o `flush` dos testes de concorrência usa TRUNCATE. O REVOKE de
# privilégios (dois papéis de banco) fica para o deploy (PENDING).
#
# As instruções vão em tupla para o Django não precisar dividir o texto com `$$`.
CRIAR = (
    """
    CREATE FUNCTION economy_ledger_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'economy_wallettransaction é append-only: % bloqueado', TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER economy_wallettransaction_append_only
    BEFORE UPDATE OR DELETE ON economy_wallettransaction
    FOR EACH ROW EXECUTE FUNCTION economy_ledger_append_only()
    """,
)

REMOVER = (
    "DROP TRIGGER economy_wallettransaction_append_only ON economy_wallettransaction",
    "DROP FUNCTION economy_ledger_append_only()",
)


class Migration(migrations.Migration):
    dependencies = [("economy", "0001_initial")]

    operations = [migrations.RunSQL(sql=CRIAR, reverse_sql=REMOVER)]
