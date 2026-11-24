"""Import do catálogo (PR 3.1): lê dois arquivos locais e grava `skins` em centavos de USD.

Dados inventados (ver conftest). O preço de referência é o `suggested_price` do desgaste mais
comum (FT, depois MW, WW, BS, FN).
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from .conftest import Escrever, preco, skin

pytestmark = pytest.mark.django_db

NOME = "AK-47 | Teste"


def _importar(c: Path, p: Path) -> Any:
    from apps.catalog.importer import import_catalog

    return import_catalog(c, p)


def _skins() -> Any:
    from apps.catalog.models import Skin

    return Skin.objects


def _erro() -> type[Exception]:
    from apps.catalog.importer import CatalogImportError

    return CatalogImportError


def _ft(valor: float | None) -> list[dict[str, Any]]:
    """Snapshot com só o preço da Field-Tested da skin de teste."""
    return [preco(NOME, "Field-Tested", valor)]


def _uma(escrever: Escrever, precos: list[dict[str, Any]]) -> tuple[Path, Path]:
    """Catálogo de uma skin (`skin-1`) com os preços dados."""
    return escrever([skin("skin-1", NOME)], precos)


def test_cria_a_skin_com_o_preco_do_desgaste_mais_comum(escrever: Escrever) -> None:
    c, p = escrever(
        [skin("skin-1", NOME, collections=["Coleção A", "Coleção B"])],
        [
            preco(NOME, "Factory New", 90.00),
            preco(NOME, "Field-Tested", 12.34),
            preco(NOME, "Battle-Scarred", 5.00),
        ],
    )

    relatorio = _importar(c, p)

    s = _skins().get(external_id="skin-1")
    assert s.reference_price == 1234
    assert (s.weapon, s.name, s.rarity) == ("AK-47", NOME, "Classified")
    assert s.collection == "Coleção A"
    assert (s.min_float, s.max_float) == (Decimal("0"), Decimal("1"))
    assert (s.active, s.image_url, s.image_source) == (True, "", "none")
    assert relatorio.created == 1


def test_sem_field_tested_cai_para_o_desgaste_seguinte(escrever: Escrever) -> None:
    c, p = escrever(
        [skin("skin-1", NOME, wears=["Factory New", "Minimal Wear", "Well-Worn"])],
        [
            preco(NOME, "Factory New", 90.00),
            preco(NOME, "Minimal Wear", 40.00),
            preco(NOME, "Well-Worn", 20.00),
        ],
    )

    _importar(c, p)

    assert _skins().get(external_id="skin-1").reference_price == 4000


def test_o_preco_decimal_nunca_passa_por_float(escrever: Escrever) -> None:
    """1.005 em float é 1.00499...: arredondar daria 100. Em Decimal, metade sobe: 101."""
    c, p = _uma(escrever, _ft(1.005))

    _importar(c, p)

    assert _skins().get(external_id="skin-1").reference_price == 101


def test_preco_so_de_outro_desgaste_nao_serve_como_referencia(escrever: Escrever) -> None:
    """A skin tem FT no catálogo, mas a Skinport só tem preço de FN: sem preço de referência."""
    c, p = _uma(escrever, [preco(NOME, "Factory New", 90.00)])

    relatorio = _importar(c, p)

    assert _skins().count() == 0
    assert relatorio.no_price == [NOME]


def test_skins_especiais_nao_sao_importadas(escrever: Escrever) -> None:
    nomes = [NOME, "★ Faca | Teste", "StatTrak™ AK-47 | Teste", "Souvenir AWP | Teste"]
    catalogo = [skin(f"skin-{i}", n) for i, n in enumerate(nomes, start=1)]
    c, p = escrever(catalogo, [preco(n, "Field-Tested", 10.00) for n in nomes])

    relatorio = _importar(c, p)

    assert list(_skins().values_list("external_id", flat=True)) == ["skin-1"]
    assert relatorio.excluded == 3


def test_skin_nova_sem_preco_nao_e_criada_e_vai_para_o_relatorio(escrever: Escrever) -> None:
    c, p = escrever(
        [skin("skin-1", "AK-47 | Com Preco"), skin("skin-2", "AK-47 | Sem Preco")],
        [preco("AK-47 | Com Preco", "Field-Tested", 10.00)],
    )

    relatorio = _importar(c, p)

    assert list(_skins().values_list("external_id", flat=True)) == ["skin-1"]
    assert relatorio.no_price == ["AK-47 | Sem Preco"]


def test_preco_nulo_no_snapshot_conta_como_sem_preco(escrever: Escrever) -> None:
    c, p = _uma(escrever, _ft(None))

    relatorio = _importar(c, p)

    assert _skins().count() == 0
    assert relatorio.no_price == [NOME]


def test_sem_colecao_fica_em_branco(escrever: Escrever) -> None:
    c, p = escrever([skin("skin-1", NOME, collections=[])], _ft(10.00))

    _importar(c, p)

    assert _skins().get(external_id="skin-1").collection == ""


def test_nomes_repetidos_com_ids_diferentes_viram_duas_skins_com_o_mesmo_preco(
    escrever: Escrever,
) -> None:
    c, p = escrever([skin("skin-1", NOME), skin("skin-2", NOME)], _ft(10.00))

    _importar(c, p)

    assert sorted(_skins().values_list("reference_price", flat=True)) == [1000, 1000]


def test_importar_de_novo_nao_cria_nem_altera_nada(escrever: Escrever) -> None:
    c, p = escrever(
        [skin("skin-1", "AK-47 | A"), skin("skin-2", "AK-47 | B")],
        [preco("AK-47 | A", "Field-Tested", 10.00), preco("AK-47 | B", "Field-Tested", 20.00)],
    )
    _importar(c, p)

    segunda = _importar(c, p)

    assert (segunda.created, segunda.updated, segunda.unchanged) == (0, 0, 2)
    assert _skins().count() == 2


def test_preco_novo_no_snapshot_atualiza_a_skin(escrever: Escrever) -> None:
    _importar(*_uma(escrever, _ft(10.00)))

    relatorio = _importar(*_uma(escrever, _ft(11.50)))

    assert _skins().get(external_id="skin-1").reference_price == 1150
    assert (relatorio.created, relatorio.updated, relatorio.unchanged) == (0, 1, 0)


def test_skin_que_perdeu_o_preco_fica_inativa_com_o_ultimo_preco(escrever: Escrever) -> None:
    _importar(*_uma(escrever, _ft(10.00)))

    relatorio = _importar(*_uma(escrever, []))

    s = _skins().get(external_id="skin-1")
    assert (s.active, s.reference_price) == (False, 1000)
    assert relatorio.deactivated == 1


def test_skin_inativa_volta_a_ficar_ativa_quando_o_preco_reaparece(escrever: Escrever) -> None:
    _importar(*_uma(escrever, _ft(10.00)))
    _importar(*_uma(escrever, []))

    _importar(*_uma(escrever, _ft(12.00)))

    s = _skins().get(external_id="skin-1")
    assert (s.active, s.reference_price) == (True, 1200)


def test_linha_invalida_aborta_tudo_e_nada_e_gravado(escrever: Escrever) -> None:
    """A 1ª skin é boa, a 2ª tem min_float >= max_float: nenhuma das duas entra."""
    c, p = escrever(
        [
            skin("skin-1", "AK-47 | Boa"),
            skin("skin-2", "AK-47 | Ruim", min_float=0.8, max_float=0.2),
        ],
        [preco("AK-47 | Boa", "Field-Tested", 10.00), preco("AK-47 | Ruim", "Field-Tested", 10.00)],
    )

    with pytest.raises(_erro()) as erro:
        _importar(c, p)

    assert "skin-2" in str(erro.value)
    assert _skins().count() == 0


def test_float_fora_de_zero_a_um_aborta(escrever: Escrever) -> None:
    c, p = escrever([skin("skin-1", NOME, max_float=1.5)], _ft(10.00))

    with pytest.raises(_erro()):
        _importar(c, p)

    assert _skins().count() == 0


@pytest.mark.parametrize("sugerido", [0, -5.0, 1e12])
def test_preco_nao_positivo_ou_acima_do_teto_aborta(escrever: Escrever, sugerido: float) -> None:
    c, p = _uma(escrever, _ft(sugerido))

    with pytest.raises(_erro()):
        _importar(c, p)

    assert _skins().count() == 0


def test_nan_no_snapshot_aborta(escrever: Escrever) -> None:
    c, p = _uma(escrever, [])
    p.write_text(
        '[{"market_hash_name": "AK-47 | Teste (Field-Tested)", "suggested_price": NaN}]',
        encoding="utf-8",
    )

    with pytest.raises(_erro()):
        _importar(c, p)

    assert _skins().count() == 0


def test_campo_obrigatorio_ausente_no_catalogo_aborta_e_diz_qual_skin(
    escrever: Escrever,
) -> None:
    quebrada = skin("skin-9", NOME)
    del quebrada["rarity"]
    c, p = escrever([quebrada], _ft(10.00))

    with pytest.raises(_erro()) as erro:
        _importar(c, p)

    assert "skin-9" in str(erro.value)
    assert _skins().count() == 0


@pytest.mark.parametrize("conteudo", ["", "{não é json", '{"nao": "uma lista"}'])
def test_arquivo_malformado_aborta(escrever: Escrever, conteudo: str) -> None:
    c, p = _uma(escrever, _ft(1.00))
    c.write_text(conteudo, encoding="utf-8")

    with pytest.raises(_erro()):
        _importar(c, p)

    assert _skins().count() == 0


def test_arquivo_inexistente_aborta(tmp_path: Path) -> None:
    with pytest.raises(_erro()):
        _importar(tmp_path / "nao-existe.json", tmp_path / "tambem-nao.json")


def test_o_comando_importa_e_imprime_o_resumo(escrever: Escrever, capsys: Any) -> None:
    c, p = _uma(escrever, _ft(10.00))

    call_command("import_catalog", catalog=str(c), prices=str(p))

    assert _skins().count() == 1
    assert "1 criadas" in capsys.readouterr().out


def test_o_comando_sai_com_erro_se_o_import_falha(escrever: Escrever) -> None:
    c, p = _uma(escrever, [])
    c.write_text(json.dumps({"nao": "uma lista"}), encoding="utf-8")

    with pytest.raises(CommandError):
        call_command("import_catalog", catalog=str(c), prices=str(p))
