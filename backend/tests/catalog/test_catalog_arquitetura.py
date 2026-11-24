"""Testes de arquitetura do catálogo: independente, sem float em dinheiro, sem dados no repo."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
APP = RAIZ / "backend" / "apps" / "catalog"


def _codigo() -> dict[str, str]:
    return {a.name: a.read_text(encoding="utf-8") for a in APP.rglob("*.py")}


def test_catalog_nao_importa_outros_apps_de_jogo() -> None:
    """Núcleo não importa núcleo: o catálogo é global e não conhece usuário, sala nem carteira."""
    proibidos = ("apps.accounts", "apps.rooms", "apps.economy", "apps.friends")
    assert "models.py" in _codigo(), "apps.catalog não existe"
    achados = [
        f"{nome}: {linha.strip()}"
        for nome, fonte in _codigo().items()
        for linha in fonte.splitlines()
        if linha.lstrip().startswith(("import ", "from ")) and any(p in linha for p in proibidos)
    ]

    assert achados == []


def test_dinheiro_do_catalogo_nao_usa_float() -> None:
    """GUIDELINES 1: preço é inteiro; o JSON é lido com Decimal e nunca vira float."""
    codigo = _codigo()

    assert "float(" not in codigo["rules.py"]
    assert "float(" not in codigo["importer.py"]
    assert "parse_float=Decimal" in codigo["importer.py"]
    assert "parse_constant" in codigo["importer.py"]  # NaN e Infinity viram erro


def test_os_arquivos_de_dados_ficam_fora_do_repositorio() -> None:
    """O repo é público e o catálogo e os preços são da Valve e da Skinport: nunca versionados."""
    gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "backend/data/" in gitignore
    assert list(APP.rglob("*.json")) == []
