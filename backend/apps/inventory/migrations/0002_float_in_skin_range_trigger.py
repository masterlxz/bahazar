from django.db import migrations

# O float de uma instância fica dentro de [min_float, max_float] da skin (MODELO-DE-DADOS).
# Um CHECK não cruza tabelas, então a garantia é um trigger: vale mesmo para um bug do serviço,
# um `shell` ou uma migração de dados futura. Dispara ao inserir e ao mudar o float ou a skin.
#
# As instruções vão em tupla para o Django não precisar dividir o texto com `$$`.
CRIAR = (
    """
    CREATE FUNCTION inventory_float_in_skin_range() RETURNS trigger AS $$
    DECLARE
        faixa_min numeric;
        faixa_max numeric;
    BEGIN
        SELECT min_float, max_float INTO faixa_min, faixa_max
        FROM catalog_skin WHERE id = NEW.skin_id;
        IF NEW.float_value < faixa_min OR NEW.float_value > faixa_max THEN
            RAISE EXCEPTION 'inventory_skininstance: float % fora da faixa da skin [%, %]',
                NEW.float_value, faixa_min, faixa_max;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER inventory_skininstance_float_in_skin_range
    BEFORE INSERT OR UPDATE OF float_value, skin_id ON inventory_skininstance
    FOR EACH ROW EXECUTE FUNCTION inventory_float_in_skin_range()
    """,
)

REMOVER = (
    "DROP TRIGGER inventory_skininstance_float_in_skin_range ON inventory_skininstance",
    "DROP FUNCTION inventory_float_in_skin_range()",
)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]

    operations = [migrations.RunSQL(sql=CRIAR, reverse_sql=REMOVER)]
