"""Quando o par acaba (bloquear ou desfazer a amizade), as ofertas PENDENTES dele acabam junto.

Antes, `friends.block` e `friends.remove_friend` deixavam a oferta `pending`: os itens ficavam
presos (índice `tradeitem_one_active_per_instance`) e só o aceite falhava (`NotFriends`).
Decisão do dono (2026-11-27): as duas operações cancelam, na MESMA transação, as pendentes do par
nos dois sentidos e liberam os itens. Só `pending` é tocada, só o par é tocado, e desbloquear não
restaura nada. O cenário (`cena`) é de `conftest.py`: ana e bruno são amigos, carla não.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.friends import services as friends_services
from apps.friends.models import Friendship
from apps.inventory import services as inventory_services
from apps.inventory.models import SkinInstance
from apps.trades import selectors, services
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_ofertas, tornar_amigos

pytestmark = pytest.mark.django_db


def _donos() -> dict[Any, Any]:
    return {i.pk: i.owner_id for i in SkinInstance.objects.all()}


def _retrato(oferta: Any) -> tuple[str, Any, list[bool]]:
    """Estado, fim e `active` dos itens, lidos do banco (não do objeto em memória)."""
    atual = TradeOffer.objects.get(pk=oferta.pk)
    return atual.status, atual.resolved_at, [i.active for i in atual.items.order_by("instance_id")]


def _pendentes() -> int:
    return TradeOffer.objects.filter(status="pending").count()


def _nenhum_item_preso() -> None:
    todos = SkinInstance.objects.values_list("pk", flat=True)
    assert selectors.busy_instance_ids(todos) == set()
    assert not TradeOfferItem.objects.filter(active=True).exists()


def test_bloquear_sem_oferta_nenhuma_so_bloqueia(cena: SimpleNamespace) -> None:
    friends_services.block(cena.ana, cena.bruno.username)

    relacao = Friendship.objects.get()
    assert (relacao.status, relacao.requester_id) == ("blocked", cena.ana.id)
    assert TradeOffer.objects.count() == 0


@pytest.mark.parametrize("quantas", [1, 3])
@pytest.mark.parametrize("quem_propos", ["bloqueador", "bloqueado"])
@pytest.mark.parametrize("bloqueador", ["ana", "bruno"])
def test_bloquear_cancela_todas_as_pendentes_do_par_e_libera_os_itens(
    cena: SimpleNamespace, skin: Any, bloqueador: str, quem_propos: str, quantas: int
) -> None:
    """Os dois sentidos: quem bloqueia pode ser o proponente ou o destinatário das ofertas."""
    quem_bloqueia = getattr(cena, bloqueador)
    outro = cena.bruno if bloqueador == "ana" else cena.ana
    de, para = (quem_bloqueia, outro) if quem_propos == "bloqueador" else (outro, quem_bloqueia)
    ofertas = criar_ofertas(de, para, quantas, skin)
    donos_antes = _donos()

    friends_services.block(quem_bloqueia, outro.username)

    for oferta in ofertas:
        status, fim, ativos = _retrato(oferta)
        assert status == "cancelled"
        assert fim is not None
        assert ativos == [False, False]
    assert _pendentes() == 0
    assert TradeOffer.objects.count() == quantas  # cancela, não apaga
    assert _donos() == donos_antes  # cancelar não move item
    _nenhum_item_preso()
    relacao = Friendship.objects.get()
    assert (relacao.status, relacao.requester_id) == ("blocked", quem_bloqueia.id)


def test_bloquear_cancela_os_dois_sentidos_de_uma_vez(cena: SimpleNamespace, skin: Any) -> None:
    de_ana = criar_ofertas(cena.ana, cena.bruno, 2, skin)
    de_bruno = criar_ofertas(cena.bruno, cena.ana, 1, skin)

    friends_services.block(cena.ana, cena.bruno.username)

    assert [_retrato(o)[0] for o in [*de_ana, *de_bruno]] == ["cancelled"] * 3
    _nenhum_item_preso()


@pytest.mark.parametrize("quem_remove", ["ana", "bruno"])
def test_desfazer_a_amizade_cancela_as_pendentes_e_o_item_volta_a_ficar_livre(
    cena: SimpleNamespace, quem_remove: str
) -> None:
    """a1 estava numa oferta de ana; depois do cancelamento ela pode oferecê-lo a carla."""
    de_ana = services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])
    de_bruno = services.create_offer(cena.bruno, cena.ana, [cena.b2.id], [cena.a2.id])
    removedor = getattr(cena, quem_remove)
    outro = cena.bruno if quem_remove == "ana" else cena.ana

    friends_services.remove_friend(removedor, outro.username)

    assert Friendship.objects.count() == 0
    assert [_retrato(o)[0] for o in (de_ana, de_bruno)] == ["cancelled", "cancelled"]
    _nenhum_item_preso()
    tornar_amigos(cena.ana, cena.carla)
    inventory_services.assert_movable(SkinInstance.objects.get(pk=cena.a1.pk))  # não levanta
    nova = services.create_offer(cena.ana, cena.carla, [cena.a1.id], [cena.c1.id])
    assert nova.status == "pending"


def test_oferta_de_outro_par_nao_e_cancelada(cena: SimpleNamespace, skin: Any) -> None:
    """Só o par bloqueado acaba: as ofertas de ana com carla e de carla com bruno seguem vivas.

    Cada uma divide UM jogador com o par bloqueado, para pegar um filtro que olhe só um lado.
    """
    tornar_amigos(cena.ana, cena.carla)
    tornar_amigos(cena.bruno, cena.carla)
    do_par = criar_ofertas(cena.ana, cena.bruno, 1, skin)[0]
    ana_carla = criar_ofertas(cena.ana, cena.carla, 1, skin)[0]
    carla_ana = criar_ofertas(cena.carla, cena.ana, 1, skin)[0]
    carla_bruno = criar_ofertas(cena.carla, cena.bruno, 1, skin)[0]
    bruno_carla = criar_ofertas(cena.bruno, cena.carla, 1, skin)[0]
    outras = (ana_carla, carla_ana, carla_bruno, bruno_carla)
    antes = [_retrato(o) for o in outras]

    friends_services.block(cena.ana, cena.bruno.username)

    assert _retrato(do_par)[0] == "cancelled"
    assert [_retrato(o) for o in outras] == antes
    assert [r[0] for r in antes] == ["pending"] * 4
    assert [r[2] for r in antes] == [[True, True]] * 4
    assert _pendentes() == 4


def test_oferta_ja_resolvida_nao_e_tocada(cena: SimpleNamespace, skin: Any) -> None:
    """Aceita, recusada e cancelada ficam como estavam: mesmo estado, mesmo `resolved_at`."""
    aceita, recusada, cancelada = criar_ofertas(cena.ana, cena.bruno, 3, skin)
    services.accept_offer(cena.bruno, aceita.id)
    services.decline_offer(cena.bruno, recusada.id)
    services.cancel_offer(cena.ana, cancelada.id)
    pendente = criar_ofertas(cena.ana, cena.bruno, 1, skin)[0]
    resolvidas = (aceita, recusada, cancelada)
    antes = [_retrato(o) for o in resolvidas]
    donos_antes = _donos()

    friends_services.block(cena.bruno, cena.ana.username)

    assert [_retrato(o) for o in resolvidas] == antes
    assert [r[0] for r in antes] == ["accepted", "declined", "cancelled"]
    assert _retrato(pendente)[0] == "cancelled"
    assert _donos() == donos_antes  # a troca aceita continua feita


def test_desbloquear_nao_restaura_nada(cena: SimpleNamespace, skin: Any) -> None:
    ofertas = criar_ofertas(cena.ana, cena.bruno, 2, skin)
    friends_services.block(cena.ana, cena.bruno.username)

    friends_services.unblock(cena.ana, cena.bruno.username)

    assert [_retrato(o)[0] for o in ofertas] == ["cancelled", "cancelled"]
    assert _pendentes() == 0
    assert Friendship.objects.count() == 0  # nem a amizade volta
    with pytest.raises(services.NotFriends):
        services.create_offer(cena.ana, cena.bruno, [cena.a1.id], [cena.b1.id])


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("post", "bruno_02/block/"), ("delete", "bruno_02/")],
    ids=["bloquear", "remover"],
)
def test_pela_api_tambem_cancela(cena: SimpleNamespace, skin: Any, metodo: str, url: str) -> None:
    """O caminho do frontend: a rota de bloquear e a de remover amigo chegam ao mesmo efeito."""
    oferta = criar_ofertas(cena.ana, cena.bruno, 1, skin)[0]
    cliente = APIClient()
    cliente.force_authenticate(cena.ana)

    resposta = getattr(cliente, metodo)(f"/api/v1/friends/{url}")

    assert resposta.status_code == 204
    assert _retrato(oferta)[0] == "cancelled"
    _nenhum_item_preso()
