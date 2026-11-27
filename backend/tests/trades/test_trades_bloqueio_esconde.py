"""Só o BLOQUEIO esconde as ofertas de um par; desfazer a amizade não.

Decisão do dono (2026-11-27), para cumprir "bloqueado não vê nada" (SEGURANCA.md): se há uma
`Friendship` `blocked` entre os dois, em qualquer direção, a oferta some da lista e o detalhe e as
ações respondem 404, IGUAL ao de uma oferta que não existe, para os DOIS lados. Um ex-amigo sem
bloqueio continua lendo o histórico.

O bloqueio é gravado direto no ORM (`_bloquear_sem_servico`) na maioria dos testes, de propósito:
assim a oferta continua `pending` e o que se prova é o filtro de leitura, não o cancelamento de
`friends.block` (esse é de `test_trades_par_encerrado.py`).
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.friends import services as friends_services
from apps.friends.models import Friendship
from apps.inventory.models import SkinInstance
from apps.trades import services
from apps.trades.models import TradeOffer

from .conftest import criar_ofertas, tornar_amigos

TRADES_URL = "/api/v1/trades/"
UM_ID_QUALQUER = "7c0f8e1a-0000-4000-8000-000000000001"

pytestmark = pytest.mark.django_db


def _logado(usuario: Any) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


def _agir(usuario: Any, offer_id: Any, acao: str) -> Any:
    return _logado(usuario).post(
        f"{TRADES_URL}{offer_id}/{acao}/", {}, format="json", headers={"Idempotency-Key": _chave()}
    )


def _chave() -> str:
    return str(uuid.uuid4())


def _ids_da_lista(usuario: Any) -> set[str]:
    resposta = _logado(usuario).get(TRADES_URL)
    assert resposta.status_code == 200, resposta.content
    dados = resposta.json()
    assert dados["count"] == len(dados["results"])  # tudo cabe numa página
    return {o["id"] for o in dados["results"]}


def _bloquear_sem_servico(bloqueador: Any, outro: Any) -> None:
    """Grava o bloqueio como `friends.block` grava, mas SEM cancelar as ofertas."""
    Friendship.objects.filter(
        requester__in=[bloqueador, outro], addressee__in=[bloqueador, outro]
    ).update(requester=bloqueador, addressee=outro, status="blocked")


def _bloquear_por(cena: SimpleNamespace, bloqueador: str) -> None:
    """ana ou bruno bloqueia o outro (sem cancelar as ofertas)."""
    outro = cena.bruno if bloqueador == "ana" else cena.ana
    _bloquear_sem_servico(getattr(cena, bloqueador), outro)


@pytest.fixture
def historico(cena: SimpleNamespace, skin: Any) -> SimpleNamespace:
    """ana e bruno: uma pendente e uma recusada. Mais uma de ana com carla e uma de carla com
    bruno, cada uma visível a só UM dos dois (e a nenhum dos bloqueados entre si)."""
    pendente, recusada = criar_ofertas(cena.ana, cena.bruno, 2, skin)
    services.decline_offer(cena.bruno, recusada.id)
    tornar_amigos(cena.ana, cena.carla)
    tornar_amigos(cena.bruno, cena.carla)
    ana_carla = criar_ofertas(cena.ana, cena.carla, 1, skin)[0]
    carla_bruno = criar_ofertas(cena.carla, cena.bruno, 1, skin)[0]
    return SimpleNamespace(
        pendente=pendente, recusada=recusada, ana_carla=ana_carla, carla_bruno=carla_bruno
    )


@pytest.mark.parametrize("bloqueador", ["ana", "bruno"])
def test_bloqueado_e_bloqueador_nao_veem_as_ofertas_um_do_outro_na_lista(
    cena: SimpleNamespace, historico: SimpleNamespace, bloqueador: str
) -> None:
    antes_ana, antes_bruno = _ids_da_lista(cena.ana), _ids_da_lista(cena.bruno)
    assert {str(historico.pendente.id), str(historico.recusada.id)} <= antes_ana & antes_bruno
    _bloquear_por(cena, bloqueador)

    assert _ids_da_lista(cena.ana) == {str(historico.ana_carla.id)}
    assert _ids_da_lista(cena.bruno) == {str(historico.carla_bruno.id)}


def test_a_lista_de_quem_foi_bloqueado_nao_vaza_nada_do_outro(
    cena: SimpleNamespace, historico: SimpleNamespace
) -> None:
    _bloquear_sem_servico(cena.bruno, cena.ana)

    texto = _logado(cena.ana).get(TRADES_URL).content.decode()

    assert cena.bruno.username not in texto  # a oferta com carla não cita bruno
    assert str(historico.pendente.id) not in texto
    assert "carla_03" in texto  # a lista não está vazia: o que fica é só o que não é do par


@pytest.mark.parametrize("bloqueador", ["ana", "bruno"])
@pytest.mark.parametrize("quem_le", ["ana", "bruno"])
@pytest.mark.parametrize("qual", ["pendente", "recusada"])
def test_detalhe_de_oferta_de_par_bloqueado_da_o_404_dos_dois_lados(
    cena: SimpleNamespace, historico: SimpleNamespace, bloqueador: str, quem_le: str, qual: str
) -> None:
    _bloquear_por(cena, bloqueador)
    oferta = getattr(historico, qual)

    escondida = _logado(getattr(cena, quem_le)).get(f"{TRADES_URL}{oferta.id}/")
    inexistente = _logado(getattr(cena, quem_le)).get(f"{TRADES_URL}{UM_ID_QUALQUER}/")

    assert escondida.status_code == 404
    assert escondida.json() == inexistente.json()  # nem a resposta revela que ela existe


def test_a_oferta_de_outro_par_continua_com_detalhe(
    cena: SimpleNamespace, historico: SimpleNamespace
) -> None:
    _bloquear_sem_servico(cena.ana, cena.bruno)

    de_ana = _logado(cena.ana).get(f"{TRADES_URL}{historico.ana_carla.id}/")
    de_bruno = _logado(cena.bruno).get(f"{TRADES_URL}{historico.carla_bruno.id}/")

    assert (de_ana.status_code, de_bruno.status_code) == (200, 200)
    assert de_ana.json()["id"] == str(historico.ana_carla.id)


@pytest.mark.parametrize("bloqueador", ["ana", "bruno"])
@pytest.mark.parametrize(
    ("acao", "ator"),
    [("accept", "bruno"), ("decline", "bruno"), ("cancel", "ana")],
)
def test_aceitar_recusar_e_cancelar_oferta_de_par_bloqueado_da_404_e_nada_muda(
    cena: SimpleNamespace, historico: SimpleNamespace, bloqueador: str, acao: str, ator: str
) -> None:
    _bloquear_por(cena, bloqueador)
    donos_antes = {i.pk: i.owner_id for i in SkinInstance.objects.all()}

    escondida = _agir(getattr(cena, ator), historico.pendente.id, acao)
    inexistente = _agir(getattr(cena, ator), UM_ID_QUALQUER, acao)

    assert escondida.status_code == 404
    assert escondida.json() == inexistente.json()
    assert escondida.json()["code"] == "offer_not_found"
    assert TradeOffer.objects.get(pk=historico.pendente.pk).status == "pending"
    assert {i.pk: i.owner_id for i in SkinInstance.objects.all()} == donos_antes


@pytest.mark.parametrize("acao", ["accept", "decline", "cancel"])
def test_o_servico_tambem_nao_acha_a_oferta_de_par_bloqueado(
    cena: SimpleNamespace, historico: SimpleNamespace, acao: str
) -> None:
    _bloquear_sem_servico(cena.ana, cena.bruno)
    funcao, ator = {
        "accept": (services.accept_offer, cena.bruno),
        "decline": (services.decline_offer, cena.bruno),
        "cancel": (services.cancel_offer, cena.ana),
    }[acao]

    with pytest.raises(services.OfferNotFound):
        funcao(ator, historico.pendente.id)


# --- só o bloqueio esconde ---------------------------------------------------------------------


@pytest.mark.parametrize("relacao", ["amigos", "pedido_pendente", "sem_relacao"])
def test_sem_bloqueio_as_ofertas_continuam_visiveis_dos_dois_lados(
    cena: SimpleNamespace, historico: SimpleNamespace, relacao: str
) -> None:
    """Ex-amigo (sem relação) e pedido pendente não escondem; a oferta pendente segue legível."""
    entre_eles = Friendship.objects.filter(
        requester__in=[cena.ana, cena.bruno], addressee__in=[cena.ana, cena.bruno]
    )
    if relacao == "pedido_pendente":
        entre_eles.update(status="pending")
    elif relacao == "sem_relacao":
        entre_eles.delete()
    esperadas = {str(historico.pendente.id), str(historico.recusada.id)}

    assert esperadas <= _ids_da_lista(cena.ana)
    assert esperadas <= _ids_da_lista(cena.bruno)
    for quem in (cena.ana, cena.bruno):
        for oferta in (historico.pendente, historico.recusada):
            resposta = _logado(quem).get(f"{TRADES_URL}{oferta.id}/")
            assert resposta.status_code == 200, (relacao, resposta.content)
            assert len(resposta.json()["items"]) == 2


def test_ex_amigo_sem_bloqueio_nao_aceita_mas_continua_lendo(
    cena: SimpleNamespace, historico: SimpleNamespace
) -> None:
    """Amizade apagada por fora do serviço (a oferta segue pendente): ler vale, aceitar não."""
    Friendship.objects.filter(
        requester__in=[cena.ana, cena.bruno], addressee__in=[cena.ana, cena.bruno]
    ).delete()

    detalhe = _logado(cena.bruno).get(f"{TRADES_URL}{historico.pendente.id}/")
    aceite = _agir(cena.bruno, historico.pendente.id, "accept")

    assert detalhe.status_code == 200
    assert (aceite.status_code, aceite.json()["code"]) == (409, "not_friends")


def test_depois_de_desfazer_a_amizade_o_historico_continua_legivel(
    cena: SimpleNamespace, skin: Any
) -> None:
    """Pelo serviço: a aceita fica `accepted`, a pendente vira `cancelled`, e as duas se leem."""
    aceita, pendente = criar_ofertas(cena.ana, cena.bruno, 2, skin)
    services.accept_offer(cena.bruno, aceita.id)

    friends_services.remove_friend(cena.bruno, cena.ana.username)

    for quem in (cena.ana, cena.bruno):
        assert _ids_da_lista(quem) == {str(aceita.id), str(pendente.id)}
        estados = {o["id"]: o["status"] for o in _logado(quem).get(TRADES_URL).json()["results"]}
        assert estados == {str(aceita.id): "accepted", str(pendente.id): "cancelled"}
        assert _logado(quem).get(f"{TRADES_URL}{pendente.id}/").status_code == 200


def test_depois_de_bloquear_e_desbloquear_o_historico_volta_a_ser_legivel(
    cena: SimpleNamespace, skin: Any
) -> None:
    """O bloqueio esconde enquanto dura; ao desbloquear (sem amizade), vira ex-amigo: lê."""
    pendente = criar_ofertas(cena.ana, cena.bruno, 1, skin)[0]
    friends_services.block(cena.ana, cena.bruno.username)
    assert _ids_da_lista(cena.ana) == set()
    assert _ids_da_lista(cena.bruno) == set()

    friends_services.unblock(cena.ana, cena.bruno.username)

    assert _ids_da_lista(cena.ana) == {str(pendente.id)}
    assert _ids_da_lista(cena.bruno) == {str(pendente.id)}
    assert _logado(cena.bruno).get(f"{TRADES_URL}{pendente.id}/").json()["status"] == "cancelled"
