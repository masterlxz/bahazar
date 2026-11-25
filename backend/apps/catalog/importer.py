"""Import do catálogo de skins a partir de dois arquivos LOCAIS (PR 3.1) ou da API da Skinport.

- `catalog`: JSON no formato do ByMykel/CSGO-API (uma lista de skins).
- `prices`: JSON no formato da Skinport `/v1/items` (uma lista de itens de mercado).

Os dois são entrada externa e não confiável: tudo é validado, e qualquer problema aborta o
import inteiro numa transação só (nada é gravado pela metade). Os arquivos pertencem à Valve e
à Skinport e nunca entram no repositório (público).
"""

import json
from base64 import b64encode
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction

from . import rules
from .models import Skin

MAX_FILE_BYTES = 100 * 1024 * 1024
_FLOAT_STEP = Decimal("0.000000001")  # o banco guarda 9 casas decimais


class CatalogImportError(ValueError):
    """O import foi recusado; a mensagem diz o arquivo e a skin."""


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    excluded: int = 0
    no_price: list[str] = field(default_factory=list)


def _refuse_constant(value: str) -> Any:
    raise ValueError(f"constante não permitida em JSON: {value}")


def _load_list(path: Path, what: str) -> list[Any]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise CatalogImportError(f"{what}: arquivo maior que {MAX_FILE_BYTES // 2**20} MB")
        texto = path.read_text(encoding="utf-8")
        dados = json.loads(texto, parse_float=Decimal, parse_constant=_refuse_constant)
    except CatalogImportError:
        raise
    except (OSError, ValueError) as erro:
        raise CatalogImportError(f"{what}: não foi possível ler {path.name}: {erro}") from erro
    if not isinstance(dados, list):
        raise CatalogImportError(f"{what}: {path.name} deveria ser uma lista JSON")
    return dados


def _text(raw: dict[str, Any], chave: str, quem: str, limite: int) -> str:
    valor = raw.get(chave)
    if not isinstance(valor, str) or not valor:
        raise CatalogImportError(f"catálogo, {quem}: campo '{chave}' ausente ou vazio")
    if len(valor) > limite:
        raise CatalogImportError(f"catálogo, {quem}: campo '{chave}' maior que {limite}")
    return valor


def _nested_name(raw: dict[str, Any], chave: str, quem: str, limite: int) -> str:
    objeto = raw.get(chave)
    if not isinstance(objeto, dict):
        raise CatalogImportError(f"catálogo, {quem}: campo '{chave}' ausente")
    return _text(objeto, "name", f"{quem} ({chave})", limite)


def _decimal(raw: dict[str, Any], chave: str, quem: str) -> Decimal:
    valor = raw.get(chave)
    if isinstance(valor, bool) or not isinstance(valor, int | Decimal):
        raise CatalogImportError(f"catálogo, {quem}: campo '{chave}' não é um número")
    numero = Decimal(valor)
    if not 0 <= numero <= 1:  # antes do quantize: um expoente enorme estouraria a precisão
        raise CatalogImportError(f"catálogo, {quem}: campo '{chave}' fora de 0 a 1")
    return numero.quantize(_FLOAT_STEP)


def _wears(raw: dict[str, Any], quem: str) -> list[str]:
    lista = raw.get("wears")
    if not isinstance(lista, list):
        raise CatalogImportError(f"catálogo, {quem}: campo 'wears' ausente")
    return [_text(w, "name", f"{quem} (wears)", 64) for w in lista if isinstance(w, dict)]


def _collection(raw: dict[str, Any], quem: str) -> str:
    colecoes = raw.get("collections")
    if not isinstance(colecoes, list) or not colecoes:
        return ""
    primeira = colecoes[0]
    if not isinstance(primeira, dict):
        raise CatalogImportError(f"catálogo, {quem}: 'collections' malformado")
    return _text(primeira, "name", f"{quem} (collections)", 200)


def _price_index(itens: list[Any]) -> dict[str, Any]:
    """`market_hash_name` -> `suggested_price` bruto (Decimal, int ou None). O 1º vence."""
    indice: dict[str, Any] = {}
    for item in itens:
        if isinstance(item, dict) and isinstance(item.get("market_hash_name"), str):
            indice.setdefault(item["market_hash_name"], item.get("suggested_price"))
    return indice


def _cents(bruto: Any, quem: str) -> int | None:
    if bruto is None:
        return None
    if isinstance(bruto, bool) or not isinstance(bruto, int | Decimal):
        raise CatalogImportError(f"preços, {quem}: 'suggested_price' não é um número")
    try:
        return rules.usd_to_cents(Decimal(bruto))
    except ValueError as erro:
        raise CatalogImportError(f"preços, {quem}: {erro}") from erro


def import_catalog(catalog_path: Path, prices_path: Path) -> ImportReport:
    catalogo = _load_list(catalog_path, "catálogo")
    precos = _price_index(_load_list(prices_path, "preços"))
    relatorio = ImportReport()
    vistos: set[str] = set()

    with transaction.atomic():
        existentes = {s.external_id: s for s in Skin.objects.all()}
        for posicao, raw in enumerate(catalogo, start=1):
            if not isinstance(raw, dict):
                raise CatalogImportError(f"catálogo, entrada {posicao}: não é um objeto")
            ext_id = _text(raw, "id", f"entrada {posicao}", 64)
            quem = f"skin {ext_id}"
            nome = _text(raw, "name", quem, 200)
            if not rules.is_importable_name(nome):
                relatorio.excluded += 1
                continue
            if ext_id in vistos:
                raise CatalogImportError(f"catálogo, {quem}: id repetido no arquivo")
            vistos.add(ext_id)

            campos: dict[str, Any] = {
                "weapon": _nested_name(raw, "weapon", quem, 64),
                "name": nome,
                "collection": _collection(raw, quem),
                "rarity": _nested_name(raw, "rarity", quem, 64),
                "min_float": _decimal(raw, "min_float", quem),
                "max_float": _decimal(raw, "max_float", quem),
            }
            if not 0 <= campos["min_float"] < campos["max_float"] <= 1:
                raise CatalogImportError(f"catálogo, {quem}: faixa de float inválida")

            desgaste = rules.reference_wear(_wears(raw, quem))
            centavos = (
                _cents(precos.get(rules.market_name(nome, desgaste)), quem)
                if desgaste is not None
                else None
            )
            _gravar(existentes.get(ext_id), ext_id, nome, campos, centavos, relatorio)
    return relatorio


def _gravar(
    existente: Skin | None,
    ext_id: str,
    nome: str,
    campos: dict[str, Any],
    centavos: int | None,
    relatorio: ImportReport,
) -> None:
    if centavos is None:
        relatorio.no_price.append(nome)
        if existente is None:
            return
        if existente.active:
            existente.active = False
            existente.save(update_fields=["active"])
            relatorio.deactivated += 1
        else:
            relatorio.unchanged += 1
        return

    if existente is None:
        Skin.objects.create(external_id=ext_id, reference_price=centavos, **campos)
        relatorio.created += 1
        return

    novos = {**campos, "reference_price": centavos, "active": True}
    mudou = [k for k, v in novos.items() if getattr(existente, k) != v]
    if not mudou:
        relatorio.unchanged += 1
        return
    for chave in mudou:
        setattr(existente, chave, novos[chave])
    existente.save(update_fields=mudou)
    relatorio.updated += 1


SKINPORT_ITEMS_URL = "https://api.skinport.com/v1/items"
SKINPORT_TIMEOUT_SECONDS = 30


def _build_skinport_url(app_id: int, currency: str) -> str:
    return f"{SKINPORT_ITEMS_URL}?app_id={app_id}&currency={currency}"


def _fetch_skinport_items(
    app_id: int,
    currency: str,
    client_id: str | None,
    client_secret: str | None,
) -> list[Any]:
    """Baixa /v1/items da Skinport. Requer Accept-Encoding: br. Retorna lista de dicts."""
    url = _build_skinport_url(app_id, currency)
    headers = {
        "Accept-Encoding": "br",
        "Accept": "application/json",
        "User-Agent": "bahazar-import-catalog/1.0 (+https://github.com/masterlxz/bahazar)",
    }
    if client_id and client_secret:
        token = b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"

    req = Request(url, headers=headers)  # noqa: S310 - URL is constant (Skinport API)
    try:
        with urlopen(req, timeout=SKINPORT_TIMEOUT_SECONDS) as resp:  # noqa: S310 - URL is constant (Skinport API)
            if resp.headers.get("Content-Encoding") == "br":
                import brotli
                data = brotli.decompress(resp.read())
            else:
                data = resp.read()
    except HTTPError as erro:
        if erro.code == 429:
            raise CatalogImportError(
                "Skinport API: rate limit excedido (429). "
                "Use API key própria (SKINPORT_CLIENT_ID/SECRET) e aguarde a janela resetar."
            ) from erro
        if erro.code == 406:
            raise CatalogImportError(
                "Skinport API: Accept-Encoding: br é obrigatório (406)."
            ) from erro
        if erro.code == 403:
            raise CatalogImportError(
                "Skinport API: acesso negado (403). Cloudflare pode estar bloqueando. "
                "Tente novamente ou use arquivo local (--prices)."
            ) from erro
        raise CatalogImportError(f"Skinport API: HTTP {erro.code}: {erro.reason}") from erro
    except URLError as erro:
        raise CatalogImportError(f"Skinport API: erro de rede: {erro.reason}") from erro

    try:
        itens = json.loads(data.decode("utf-8"), parse_float=Decimal)
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise CatalogImportError(f"Skinport API: resposta não é JSON válido: {erro}") from erro

    if not isinstance(itens, list):
        raise CatalogImportError("Skinport API: resposta não é uma lista")
    return itens


def import_catalog_from_api(
    catalog_path: Path,
    app_id: int,
    currency: str,
    client_id: str | None,
    client_secret: str | None,
) -> ImportReport:
    """Importa catálogo local + preços da API da Skinport."""
    catalogo = _load_list(catalog_path, "catálogo")
    precos_raw = _fetch_skinport_items(app_id, currency, client_id, client_secret)
    precos = _price_index(precos_raw)
    relatorio = ImportReport()
    vistos: set[str] = set()

    with transaction.atomic():
        existentes = {s.external_id: s for s in Skin.objects.all()}
        for posicao, raw in enumerate(catalogo, start=1):
            if not isinstance(raw, dict):
                raise CatalogImportError(f"catálogo, entrada {posicao}: não é um objeto")
            ext_id = _text(raw, "id", f"entrada {posicao}", 64)
            quem = f"skin {ext_id}"
            nome = _text(raw, "name", quem, 200)
            if not rules.is_importable_name(nome):
                relatorio.excluded += 1
                continue
            if ext_id in vistos:
                raise CatalogImportError(f"catálogo, {quem}: id repetido no arquivo")
            vistos.add(ext_id)

            campos: dict[str, Any] = {
                "weapon": _nested_name(raw, "weapon", quem, 64),
                "name": nome,
                "collection": _collection(raw, quem),
                "rarity": _nested_name(raw, "rarity", quem, 64),
                "min_float": _decimal(raw, "min_float", quem),
                "max_float": _decimal(raw, "max_float", quem),
            }
            if not 0 <= campos["min_float"] < campos["max_float"] <= 1:
                raise CatalogImportError(f"catálogo, {quem}: faixa de float inválida")

            desgaste = rules.reference_wear(_wears(raw, quem))
            centavos = (
                _cents(precos.get(rules.market_name(nome, desgaste)), quem)
                if desgaste is not None
                else None
            )
            _gravar(existentes.get(ext_id), ext_id, nome, campos, centavos, relatorio)
    return relatorio
