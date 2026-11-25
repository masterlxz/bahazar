"""Testes de arquitetura do mercado: regras puras, estados do modelo e posse pelo inventory."""

import re
from pathlib import Path

APPS = Path(__file__).resolve().parents[2] / "apps"
APP = APPS / "marketplace"


def _codigo() -> dict[str, str]:
    return {
        str(a.relative_to(APP)): a.read_text(encoding="utf-8")
        for a in APP.rglob("*.py")
        if "migrations" not in a.parts
    }


def _imports(fonte: str) -> list[str]:
    return [
        linha.strip()
        for linha in fonte.splitlines()
        if linha.lstrip().startswith(("import ", "from "))
    ]


def test_o_app_do_mercado_existe_com_as_camadas_esperadas() -> None:
    codigo = _codigo()

    assert {"models.py", "services.py", "selectors.py", "views.py"} <= set(codigo)


def test_rules_nao_importa_django_nem_outros_apps() -> None:
    """GUIDELINES 5: a regra pura roda sem banco e sem framework."""
    fonte = _codigo()["rules.py"]

    achados = [linha for linha in _imports(fonte) if "django" in linha or "apps." in linha]

    assert achados == []


def test_os_estados_de_rules_sao_os_mesmos_do_modelo() -> None:
    """`rules` é puro e repete os textos dos estados; este teste impede que se separem."""
    from apps.marketplace import rules  # type: ignore[import-not-found, unused-ignore]
    from apps.marketplace.models import ListingStatus  # type: ignore[import-not-found, unused-ignore]

    de_rules = (rules.ACTIVE, rules.SOLD, rules.CANCELLED)

    assert de_rules == tuple(ListingStatus)
    assert set(de_rules) == set(ListingStatus.values)


def test_o_mercado_nao_importa_trades() -> None:
    """Módulo não importa módulo: a única ponte é a guarda registrada em `inventory`."""
    for nome, fonte in _codigo().items():
        assert not any("apps.trades" in linha for linha in _imports(fonte)), nome


def test_nenhum_arquivo_do_mercado_escreve_o_dono_do_item() -> None:
    """GUIDELINES 2: só `inventory.services` muda o dono. O mercado só lê e recusa."""
    escrita_direta = re.compile(r"\.owner\s*=[^=]|\.owner_id\s*=[^=]|\.update\([^)]*owner")
    achados = [nome for nome, fonte in _codigo().items() if escrita_direta.search(fonte)]

    assert achados == []
