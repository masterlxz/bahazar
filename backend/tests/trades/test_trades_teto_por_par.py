"""Teto de ofertas pendentes por PAR e por SENTIDO (proponente -> destinatário).

Decisão do dono (2026-11-27): um amigo podia reservar itens de outro com até 20 ofertas pendentes
(o teto era só por proponente). O novo teto é `rules.PENDING_PER_PAIR_LIMIT` (3, HIPÓTESE sem
fonte) do MESMO proponente para o MESMO destinatário: bruno->ana tem a cota própria. Só `pending`
conta, e o teto de 20 por proponente (já existente) é conferido ANTES.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.trades import rules, selectors, services
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_instancia, criar_ofertas, tornar_amigos

TRADES_URL = "/api/v1/trades/"

pytestmark = pytest.mark.django_db


def _pendentes_de_ana_para(destinatario: Any, ana: Any) -> int:
    return TradeOffer.objects.filter(proposer=ana, recipient=destinatario, status="pending").count()


# --- regra pura --------------------------------------------------------------------------------


def test_o_teto_por_par_e_3_e_menor_que_o_teto_por_proponente() -> None:
    """3 é HIPÓTESE do dono (2026-11-27), sem fonte: mudar a constante muda este teste de propósito.

    E tem de ser menor que o teto por proponente, senão não limitaria nada.
    """
    assert rules.PENDING_PER_PAIR_LIMIT == 3
    assert rules.PENDING_PER_PAIR_LIMIT < rules.MAX_PENDING_PER_PROPOSER


@pytest.mark.parametrize(
    ("relativo_ao_teto", "estoura"),
    [(-1, False), (0, True), (1, True)],
    ids=["uma abaixo do teto", "no teto", "acima do teto"],
)
def test_nova_oferta_so_cabe_abaixo_do_teto_por_par(relativo_ao_teto: int, estoura: bool) -> None:
    pendentes = rules.PENDING_PER_PAIR_LIMIT + relativo_ao_teto

    assert rules.pending_pair_limit_exceeded(pendentes) is estoura


def test_nenhuma_pendente_nunca_estoura_o_teto_por_par() -> None:
    assert rules.pending_pair_limit_exceeded(0) is False


# --- o seletor ---------------------------------------------------------------------------------


def test_pending_count_between_conta_so_pendentes_do_mesmo_sentido(
    cena: SimpleNamespace, skin: Any
) -> None:
    tornar_amigos(cena.ana, cena.carla)
    criar_ofertas(cena.ana, cena.bruno, 2, skin)
    resolvida = criar_ofertas(cena.ana, cena.bruno, 1, skin)[0]
    services.cancel_offer(cena.ana, resolvida.id)
    criar_ofertas(cena.bruno, cena.ana, 1, skin)
    criar_ofertas(cena.ana, cena.carla, 1, skin)

    assert selectors.pending_count_between(cena.ana, cena.bruno) == 2
    assert selectors.pending_count_between(cena.bruno, cena.ana) == 1
    assert selectors.pending_count_between(cena.ana, cena.carla) == 1
    assert selectors.pending_count_between(cena.carla, cena.ana) == 0
    assert selectors.pending_count_between(cena.bruno, cena.carla) == 0


# --- o serviço ---------------------------------------------------------------------------------


def test_a_ultima_vaga_do_par_passa_e_a_seguinte_e_recusada_sem_gravar_nada(
    cena: SimpleNamespace, skin: Any
) -> None:
    limite = rules.PENDING_PER_PAIR_LIMIT

    criar_ofertas(cena.ana, cena.bruno, limite, skin)

    assert _pendentes_de_ana_para(cena.bruno, cena.ana) == limite
    with pytest.raises(services.TooManyPendingForRecipient):
        criar_ofertas(cena.ana, cena.bruno, 1, skin)
    assert TradeOffer.objects.count() == limite
    assert TradeOfferItem.objects.count() == 2 * limite


def test_o_erro_novo_e_um_erro_de_troca_com_codigo_proprio() -> None:
    assert issubclass(services.TooManyPendingForRecipient, services.TradeError)
    assert services.TooManyPendingForRecipient.code == "too_many_pending_for_recipient"
    assert services.TooManyPendingForRecipient.code != services.TooManyPendingOffers.code


def test_outro_destinatario_nao_gasta_a_cota_do_par(cena: SimpleNamespace, skin: Any) -> None:
    tornar_amigos(cena.ana, cena.carla)
    criar_ofertas(cena.ana, cena.bruno, rules.PENDING_PER_PAIR_LIMIT, skin)

    para_a_carla = criar_ofertas(cena.ana, cena.carla, rules.PENDING_PER_PAIR_LIMIT, skin)

    assert len(para_a_carla) == rules.PENDING_PER_PAIR_LIMIT
    assert _pendentes_de_ana_para(cena.carla, cena.ana) == rules.PENDING_PER_PAIR_LIMIT


def test_o_sentido_oposto_tem_a_cota_propria(cena: SimpleNamespace, skin: Any) -> None:
    """ana encheu a cota ana->bruno; bruno->ana ainda tem as três dele."""
    criar_ofertas(cena.ana, cena.bruno, rules.PENDING_PER_PAIR_LIMIT, skin)

    de_volta = criar_ofertas(cena.bruno, cena.ana, rules.PENDING_PER_PAIR_LIMIT, skin)

    assert len(de_volta) == rules.PENDING_PER_PAIR_LIMIT
    with pytest.raises(services.TooManyPendingForRecipient):
        criar_ofertas(cena.bruno, cena.ana, 1, skin)


@pytest.mark.parametrize("encerrar", ["recusar", "cancelar", "aceitar"])
def test_encerrar_uma_oferta_do_par_libera_a_vaga(
    cena: SimpleNamespace, skin: Any, encerrar: str
) -> None:
    ofertas = criar_ofertas(cena.ana, cena.bruno, rules.PENDING_PER_PAIR_LIMIT, skin)
    with pytest.raises(services.TooManyPendingForRecipient):
        criar_ofertas(cena.ana, cena.bruno, 1, skin)
    if encerrar == "recusar":
        services.decline_offer(cena.bruno, ofertas[0].id)
    elif encerrar == "cancelar":
        services.cancel_offer(cena.ana, ofertas[0].id)
    else:
        services.accept_offer(cena.bruno, ofertas[0].id)

    nova = criar_ofertas(cena.ana, cena.bruno, 1, skin)[0]

    assert nova.status == "pending"
    assert _pendentes_de_ana_para(cena.bruno, cena.ana) == rules.PENDING_PER_PAIR_LIMIT


def test_com_os_dois_tetos_estourados_vale_o_erro_do_teto_por_proponente(
    cena: SimpleNamespace, skin: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O teto por proponente é conferido primeiro: quem já tem o máximo recebe o erro de sempre."""
    monkeypatch.setattr(rules, "MAX_PENDING_PER_PROPOSER", rules.PENDING_PER_PAIR_LIMIT)
    criar_ofertas(cena.ana, cena.bruno, rules.PENDING_PER_PAIR_LIMIT, skin)

    with pytest.raises(services.TooManyPendingOffers):
        criar_ofertas(cena.ana, cena.bruno, 1, skin)


# --- a API -------------------------------------------------------------------------------------


def test_a_api_responde_409_com_o_codigo_novo_na_oferta_alem_da_cota(
    cena: SimpleNamespace, skin: Any
) -> None:
    criar_ofertas(cena.ana, cena.bruno, rules.PENDING_PER_PAIR_LIMIT, skin)
    cliente = APIClient()
    cliente.force_authenticate(cena.ana)
    corpo = {
        "recipient": "bruno_02",
        "offered": [str(criar_instancia(cena.ana, skin).pk)],
        "requested": [str(criar_instancia(cena.bruno, skin).pk)],
    }

    resposta = cliente.post(
        TRADES_URL, corpo, format="json", headers={"Idempotency-Key": str(uuid.uuid4())}
    )

    assert resposta.status_code == 409
    assert resposta.json()["code"] == "too_many_pending_for_recipient"
    assert TradeOffer.objects.count() == rules.PENDING_PER_PAIR_LIMIT
