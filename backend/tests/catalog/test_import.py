"""Import do catálogo (PR 3.1): lê dois arquivos locais e grava `skins` em centavos de USD.

Dados inventados (ver conftest). O preço de referência é o `suggested_price` do desgaste mais
comum (FT, depois MW, WW, BS, FN).
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

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


# --- Testes do modo API (import_catalog_from_api) ---


def _mock_skinport_response(items: list[dict[str, Any]]) -> MagicMock:
    """Cria um mock de resposta HTTP com brotli comprimido."""
    import brotli

    resposta = MagicMock()
    resposta.headers = {"Content-Encoding": "br"}
    resposta.read.return_value = brotli.compress(json.dumps(items).encode("utf-8"))
    return resposta


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_cria_skin_com_preco(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    mock_urlopen.return_value.__enter__.return_value = _mock_skinport_response(
        [{"market_hash_name": f"{NOME} (Field-Tested)", "suggested_price": 12.34}]
    )

    relatorio = import_catalog_from_api(
        c, app_id=730, currency="USD", client_id=None, client_secret=None
    )

    assert relatorio.created == 1
    from apps.catalog.models import Skin
    assert Skin.objects.get(external_id="skin-1").reference_price == 1234


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_envia_authorization_com_api_key(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    mock_urlopen.return_value.__enter__.return_value = _mock_skinport_response(
        [{"market_hash_name": f"{NOME} (Field-Tested)", "suggested_price": 10.00}]
    )

    import_catalog_from_api(
        c, app_id=730, currency="USD", client_id="test-id", client_secret="test-secret"
    )

    # Verifica se o header Authorization foi enviado
    args, kwargs = mock_urlopen.call_args
    request = args[0]
    assert "Authorization" in request.headers
    assert request.headers["Authorization"].startswith("Basic ")


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_rate_limit_429_lanca_erro(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import CatalogImportError, import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    erro_429 = HTTPError("url", 429, "Too Many Requests", {}, None)
    mock_urlopen.side_effect = erro_429

    with pytest.raises(CatalogImportError) as exc:
        import_catalog_from_api(
            c, app_id=730, currency="USD", client_id=None, client_secret=None
        )
    assert "rate limit excedido" in str(exc.value).lower()


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_406_accept_encoding_obrigatorio(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import CatalogImportError, import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    erro_406 = HTTPError("url", 406, "Not Acceptable", {}, None)
    mock_urlopen.side_effect = erro_406

    with pytest.raises(CatalogImportError) as exc:
        import_catalog_from_api(
            c, app_id=730, currency="USD", client_id=None, client_secret=None
        )
    assert "accept-encoding: br" in str(exc.value).lower()


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_403_cloudflare_bloqueia(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import CatalogImportError, import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    erro_403 = HTTPError("url", 403, "Forbidden", {}, None)
    mock_urlopen.side_effect = erro_403

    with pytest.raises(CatalogImportError) as exc:
        import_catalog_from_api(
            c, app_id=730, currency="USD", client_id=None, client_secret=None
        )
    assert "cloudflare" in str(exc.value).lower()


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_resposta_nao_lista_lanca_erro(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import CatalogImportError, import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    mock_urlopen.return_value.__enter__.return_value = _mock_skinport_response({"nao": "uma lista"})

    with pytest.raises(CatalogImportError) as exc:
        import_catalog_from_api(
            c, app_id=730, currency="USD", client_id=None, client_secret=None
        )
    assert "não é uma lista" in str(exc.value)


@patch("apps.catalog.importer.urlopen")
def test_import_catalog_from_api_rede_erro_lanca_erro(
    mock_urlopen: MagicMock, escrever: Escrever
) -> None:
    from apps.catalog.importer import CatalogImportError, import_catalog_from_api

    c = escrever([skin("skin-1", NOME)], [])[0]
    mock_urlopen.side_effect = URLError("conexão recusada")

    with pytest.raises(CatalogImportError) as exc:
        import_catalog_from_api(
            c, app_id=730, currency="USD", client_id=None, client_secret=None
        )
    assert "erro de rede" in str(exc.value).lower()


def test_comando_com_fetch_chama_import_catalog_from_api(escrever: Escrever, capsys: Any) -> None:
    from django.core.management import call_command

    c = escrever([skin("skin-1", NOME)], [])[0]

    report = type(
        "R",
        (),
        {
            "created": 1,
            "updated": 0,
            "unchanged": 0,
            "deactivated": 0,
            "excluded": 0,
            "no_price": [],
        },
    )()

    with patch("apps.catalog.importer.import_catalog_from_api") as mock_import:
        mock_import.return_value = report

        call_command("import_catalog", catalog=str(c), fetch=True, app_id=730, currency="USD")

        mock_import.assert_called_once()
        assert mock_import.call_args[1]["catalog_path"] == c
        assert mock_import.call_args[1]["app_id"] == 730
        assert mock_import.call_args[1]["currency"] == "USD"


def test_comando_fetch_sem_catalog_falha(escrever: Escrever) -> None:
    from django.core.management import call_command
    from django.core.management.base import CommandError

    c = escrever([skin("skin-1", NOME)], [])[0]

    with pytest.raises(CommandError) as exc:
        call_command(
            "import_catalog", catalog=str(c), fetch=True, prices=str(c)
        )  # --prices com --fetch
    assert "--prices não deve ser usado com --fetch" in str(exc.value)


def test_comando_sem_fetch_sem_prices_falha(escrever: Escrever) -> None:
    from django.core.management import call_command
    from django.core.management.base import CommandError

    c = escrever([skin("skin-1", NOME)], [])[0]

    with pytest.raises(CommandError) as exc:
        call_command("import_catalog", catalog=str(c), fetch=False)
    assert "--prices é obrigatório sem --fetch" in str(exc.value)
