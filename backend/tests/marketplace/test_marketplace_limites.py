"""Limites do mercado: throttle por escopo, teto do preço e vitrine sem anúncio inválido.

Decisões do dono (2026-11-26): a leitura da vitrine tem escopo próprio de throttle; o teto do
preço é o maior inteiro que o JavaScript do frontend representa sem arredondar (`2**53 - 1`). O
valor 120/min da leitura é HIPÓTESE (sem fonte), como o 30/min de criar e o 60/min de cancelar.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from django.conf import settings
from django.utils import timezone

from apps.inventory.models import SkinInstance
from apps.marketplace import rules

from .conftest import LISTINGS_URL, anunciar, logado

UM_ID_QUALQUER = "7c0f8e1a-0000-4000-8000-000000000001"
LIMITE_LEITURA = 120

pytestmark = pytest.mark.django_db


# --- throttle por escopo -----------------------------------------------------------------------


def _criar_vazio(cliente: Any) -> int:
    """POST de criar com corpo vazio: 400 barato, mas conta para o throttle (ele roda antes)."""
    status_code: int = cliente.post(LISTINGS_URL, {}, format="json").status_code
    return status_code


def test_os_tres_escopos_do_mercado_tem_taxa_configurada() -> None:
    configuracao: Any = settings.REST_FRAMEWORK
    taxas: dict[str, str] = configuracao["DEFAULT_THROTTLE_RATES"]

    assert taxas["market_listing_create"] == "30/min"
    assert taxas["market_listing_cancel"] == "60/min"
    assert taxas["market_listing_read"] == f"{LIMITE_LEITURA}/min"


def test_criar_anuncio_leva_429_na_31a_tentativa_por_minuto(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)

    estados = [_criar_vazio(ana) for _ in range(31)]

    assert estados == [400] * 30 + [429]


def test_cancelar_leva_429_na_61a_tentativa_por_minuto(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)
    url = f"{LISTINGS_URL}{UM_ID_QUALQUER}/cancel/"

    estados = [ana.post(url, {}, format="json").status_code for _ in range(61)]
    # 404: o anúncio não existe; a resposta é barata e conta para o throttle, que roda antes

    assert estados == [404] * 60 + [429]


def test_ler_a_vitrine_nao_gasta_a_cota_de_criar(cena: SimpleNamespace) -> None:
    """Sem escopo próprio de leitura, 30 GETs esgotam o balde do POST e o anúncio leva 429."""
    ana = logado(cena.ana)

    leituras = [ana.get(LISTINGS_URL).status_code for _ in range(30)]

    assert leituras == [200] * 30
    assert _criar_vazio(ana) == 400


def test_a_leitura_tem_limite_proprio_e_o_detalhe_conta_nele(cena: SimpleNamespace) -> None:
    """A lista e o detalhe dividem o balde de leitura; a 121ª leva 429 e criar continua livre."""
    ana = logado(cena.ana)
    detalhe = f"{LISTINGS_URL}{UM_ID_QUALQUER}/"

    metade = LIMITE_LEITURA // 2
    estados = [ana.get(LISTINGS_URL).status_code for _ in range(metade)]
    estados += [ana.get(detalhe).status_code for _ in range(metade)]
    estados.append(ana.get(LISTINGS_URL).status_code)

    assert estados == [200] * metade + [404] * metade + [429]
    assert _criar_vazio(ana) == 400


def test_o_limite_de_leitura_e_por_usuario(cena: SimpleNamespace) -> None:
    ana, bruno = logado(cena.ana), logado(cena.bruno)
    for _ in range(LIMITE_LEITURA):
        ana.get(LISTINGS_URL)

    assert ana.get(LISTINGS_URL).status_code == 429
    assert bruno.get(LISTINGS_URL).status_code == 200


# --- teto do preço -----------------------------------------------------------------------------


def test_o_teto_do_preco_e_o_maior_inteiro_exato_do_javascript() -> None:
    assert rules.MAX_PRICE == 2**53 - 1


@pytest.mark.parametrize(
    ("valor", "vale"),
    [(1, True), (2**53 - 1, True), (2**53, False), (2**63 - 1, False), (0, False)],
)
def test_price_is_valid_nas_bordas_do_teto(valor: int, vale: bool) -> None:
    assert rules.price_is_valid(valor) is vale


def test_a_api_aceita_o_teto_e_recusa_um_a_mais(cena: SimpleNamespace) -> None:
    ana = logado(cena.ana)

    no_teto = ana.post(
        LISTINGS_URL, {"instance_id": str(cena.a1.pk), "price": 2**53 - 1}, format="json"
    )
    acima = ana.post(LISTINGS_URL, {"instance_id": str(cena.a2.pk), "price": 2**53}, format="json")

    assert no_teto.status_code == 201, no_teto.content
    assert no_teto.json()["price"] == 2**53 - 1
    assert acima.status_code == 400
    assert acima.json()["code"] == "invalid_price"


# --- a vitrine só mostra anúncio que ainda vale --------------------------------------------------


def _ids_da_vitrine(cliente: Any) -> list[str]:
    resposta = cliente.get(LISTINGS_URL)
    assert resposta.status_code == 200
    return [a["id"] for a in resposta.json()["results"]]


@pytest.mark.parametrize("mudanca", ["consumo", "dono"])
def test_item_que_saiu_do_jogo_ou_mudou_de_dono_some_da_vitrine_e_do_detalhe(
    cena: SimpleNamespace, mudanca: str
) -> None:
    """Um `UPDATE` direto, admin ou trade-up que consome o item não passa pela guarda.

    O anúncio fica `active` no banco, mas a vitrine não pode mostrar um item consumido nem um que
    já não é do vendedor: o comprador (4.4) iria bater num erro, e o anúncio mostraria lixo.
    """
    morto = anunciar(cena.ana, cena.a1)
    vivo = anunciar(cena.ana, cena.a2)
    if mudanca == "consumo":
        SkinInstance.objects.filter(pk=cena.a1.pk).update(consumed_at=timezone.now())
    else:
        SkinInstance.objects.filter(pk=cena.a1.pk).update(owner=cena.carla)
    leitor = logado(cena.bruno)

    assert _ids_da_vitrine(leitor) == [str(vivo.pk)]
    assert leitor.get(f"{LISTINGS_URL}{morto.pk}/").status_code == 404
    assert leitor.get(f"{LISTINGS_URL}{vivo.pk}/").status_code == 200


def test_o_filtro_da_vitrine_nao_esconde_anuncio_valido(cena: SimpleNamespace) -> None:
    """Dois anúncios válidos de vendedores diferentes continuam aparecendo."""
    a = anunciar(cena.ana, cena.a1)
    b = anunciar(cena.bruno, cena.b1)

    assert sorted(_ids_da_vitrine(logado(cena.carla))) == sorted([str(a.pk), str(b.pk)])
