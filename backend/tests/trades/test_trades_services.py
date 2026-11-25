"""Serviço de troca de itens (`apps.trades.services`), contra PostgreSQL real.

Valores esperados vêm das regras do plano: cada lado com pelo menos 1 item, só entre amigos
aceitos, só `pending` muda de estado. O cenário (`cena`) é de `conftest.py`.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from apps.friends.models import Friendship
from apps.inventory.models import SkinInstance
from apps.trades import rules, selectors, services
from apps.trades.models import TradeOffer, TradeOfferItem

from .conftest import criar_instancia, criar_relacao, tornar_amigos

pytestmark = pytest.mark.django_db


def _oferecer(de: Any, para: Any, dar: list[Any], pedir: list[Any]) -> Any:
    return services.create_offer(de, para, [i.id for i in dar], [i.id for i in pedir])


def _dono(instancia: Any) -> uuid.UUID:
    return SkinInstance.objects.get(pk=instancia.pk).owner_id


def _donos(*instancias: Any) -> list[uuid.UUID]:
    return [_dono(i) for i in instancias]


def _nada_foi_criado() -> None:
    assert TradeOffer.objects.count() == 0
    assert TradeOfferItem.objects.count() == 0


# --- criar a oferta ----------------------------------------------------------------------------


def test_cria_oferta_valida_com_dois_itens_de_um_lado_e_um_do_outro(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1, cena.a2], [cena.b1])

    oferta.refresh_from_db()
    assert (oferta.proposer_id, oferta.recipient_id) == (cena.ana.id, cena.bruno.id)
    assert oferta.status == "pending"
    assert oferta.resolved_at is None
    itens = {(i.instance_id, i.side, i.active) for i in oferta.items.all()}
    assert itens == {
        (cena.a1.id, "offered", True),
        (cena.a2.id, "offered", True),
        (cena.b1.id, "requested", True),
    }
    assert _donos(cena.a1, cena.a2, cena.b1) == [cena.ana.id, cena.ana.id, cena.bruno.id]


def test_criar_oferta_nao_move_item_nenhum(cena: SimpleNamespace) -> None:
    _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    assert _donos(cena.a1, cena.b1) == [cena.ana.id, cena.bruno.id]
    assert SkinInstance.objects.count() == 5


def test_o_destinatario_pode_propor_de_volta_com_outros_itens(cena: SimpleNamespace) -> None:
    """bruno oferece a ana: o mesmo par, em outra direção, com outros itens."""
    _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    oferta = _oferecer(cena.bruno, cena.ana, [cena.b2], [cena.a2])

    assert (oferta.proposer_id, oferta.recipient_id) == (cena.bruno.id, cena.ana.id)
    assert TradeOffer.objects.count() == 2


# --- criar a oferta: recusas (nada é gravado) --------------------------------------------------


@pytest.mark.parametrize("lado_vazio", ["oferecidos", "pedidos", "ambos"])
def test_recusa_lado_vazio(cena: SimpleNamespace, lado_vazio: str) -> None:
    dar = [] if lado_vazio in ("oferecidos", "ambos") else [cena.a1]
    pedir = [] if lado_vazio in ("pedidos", "ambos") else [cena.b1]

    with pytest.raises(services.EmptySide):
        _oferecer(cena.ana, cena.bruno, dar, pedir)

    _nada_foi_criado()


@pytest.mark.parametrize(
    "montar",
    [
        lambda c: ([c.a1, c.a1], [c.b1]),
        lambda c: ([c.a1], [c.b1, c.b1]),
        lambda c: ([c.a1, c.b1], [c.b1]),
    ],
    ids=["repetido ao oferecer", "repetido ao pedir", "mesmo item nos dois lados"],
)
def test_recusa_instancia_repetida(cena: SimpleNamespace, montar: Any) -> None:
    dar, pedir = montar(cena)

    with pytest.raises(services.DuplicateItem):
        _oferecer(cena.ana, cena.bruno, dar, pedir)

    _nada_foi_criado()


def test_recusa_auto_oferta(cena: SimpleNamespace) -> None:
    with pytest.raises(services.SelfTrade):
        _oferecer(cena.ana, cena.ana, [cena.a1], [cena.a2])

    _nada_foi_criado()


@pytest.mark.parametrize(
    "relacao", ["pendente", "bloqueado_por_mim", "bloqueado_por_ele", "nenhuma"]
)
def test_recusa_quem_nao_e_amigo_aceito(cena: SimpleNamespace, relacao: str) -> None:
    """carla não tem amizade com ana; o caso `nenhuma` é o do usuário sem relação alguma."""
    if relacao == "pendente":
        criar_relacao(cena.ana, cena.carla, "pending")
    elif relacao == "bloqueado_por_mim":
        criar_relacao(cena.ana, cena.carla, "blocked")
    elif relacao == "bloqueado_por_ele":
        criar_relacao(cena.carla, cena.ana, "blocked")

    with pytest.raises(services.NotFriends):
        _oferecer(cena.ana, cena.carla, [cena.a1], [cena.c1])

    _nada_foi_criado()


def test_amizade_aceita_pelo_lado_oposto_do_pedido_tambem_vale(cena: SimpleNamespace) -> None:
    """A direção da amizade só registra quem pediu: carla pediu e ana aceitou."""
    criar_relacao(cena.carla, cena.ana, "accepted")

    oferta = _oferecer(cena.ana, cena.carla, [cena.a1], [cena.c1])

    assert oferta.status == "pending"


@pytest.mark.parametrize(
    "montar",
    [
        lambda c: ([c.b1], [c.b2]),  # oferece item que é do destinatário
        lambda c: ([c.a1], [c.a2]),  # pede item que é do próprio proponente
        lambda c: ([c.a1], [c.c1]),  # pede item de um terceiro
        lambda c: ([c.a1], [uuid.uuid4()]),  # pede um id que não existe
    ],
    ids=["oferece item alheio", "pede item proprio", "pede item de terceiro", "id inexistente"],
)
def test_recusa_instancia_que_nao_e_do_dono_declarado(cena: SimpleNamespace, montar: Any) -> None:
    dar, pedir = montar(cena)
    dar_ids = [getattr(i, "id", i) for i in dar]
    pedir_ids = [getattr(i, "id", i) for i in pedir]

    with pytest.raises(services.ItemNotOwned):
        services.create_offer(cena.ana, cena.bruno, dar_ids, pedir_ids)

    _nada_foi_criado()


@pytest.mark.parametrize("lado", ["oferecido", "pedido"])
def test_recusa_instancia_consumida(cena: SimpleNamespace, lado: str) -> None:
    consumida = cena.a1 if lado == "oferecido" else cena.b1
    SkinInstance.objects.filter(pk=consumida.pk).update(consumed_at=datetime.now(UTC))

    with pytest.raises(services.ItemConsumed):
        _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    _nada_foi_criado()


def test_recusa_instancia_que_ja_esta_em_outra_oferta_pendente(cena: SimpleNamespace) -> None:
    _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    with pytest.raises(services.ItemAlreadyOffered):
        _oferecer(cena.ana, cena.bruno, [cena.a1, cena.a2], [cena.b2])

    assert TradeOffer.objects.count() == 1
    assert TradeOfferItem.objects.count() == 2


def test_recusa_pedir_item_que_ja_esta_em_oferta_pendente_de_outro(cena: SimpleNamespace) -> None:
    """b1 já foi pedido por ana; carla (amiga de bruno) não pode pedi-lo também."""
    tornar_amigos(cena.carla, cena.bruno)
    _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    with pytest.raises(services.ItemAlreadyOffered):
        _oferecer(cena.carla, cena.bruno, [cena.c1], [cena.b1])

    assert TradeOffer.objects.count() == 1


def test_o_indice_unico_do_banco_fecha_a_corrida_que_a_checagem_em_python_perde(
    cena: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simula a janela da corrida: a checagem em Python não vê a oferta que já existe.

    Só o índice único parcial pode recusar. O serviço traduz a violação em `ItemAlreadyOffered`
    e a oferta nova não fica gravada (o savepoint desfaz a linha da oferta).
    """
    _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])
    monkeypatch.setattr(selectors, "busy_instance_ids", lambda ids: set())

    with pytest.raises(services.ItemAlreadyOffered):
        _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b2])

    assert TradeOffer.objects.count() == 1
    assert TradeOfferItem.objects.count() == 2


# --- tetos (HIPÓTESE do coordenador: 20 itens por lado, 20 pendentes por proponente) -----------


def _itens(dono: Any, skin: Any, quantos: int) -> list[Any]:
    return [criar_instancia(dono, skin) for _ in range(quantos)]


def test_aceita_exatamente_o_teto_de_itens_em_cada_lado(cena: SimpleNamespace, skin: Any) -> None:
    n = rules.MAX_ITEMS_PER_SIDE
    dar, pedir = _itens(cena.ana, skin, n), _itens(cena.bruno, skin, n)

    oferta = _oferecer(cena.ana, cena.bruno, dar, pedir)

    assert oferta.items.count() == 2 * n


@pytest.mark.parametrize("lado", ["oferecido", "pedido"])
def test_recusa_um_item_acima_do_teto_em_um_lado_e_nao_grava_nada(
    cena: SimpleNamespace, skin: Any, lado: str
) -> None:
    n = rules.MAX_ITEMS_PER_SIDE + 1
    dar = _itens(cena.ana, skin, n if lado == "oferecido" else 1)
    pedir = _itens(cena.bruno, skin, n if lado == "pedido" else 1)

    with pytest.raises(services.TooManyItems):
        _oferecer(cena.ana, cena.bruno, dar, pedir)

    _nada_foi_criado()


@pytest.mark.parametrize("ruim", ["texto", "00000000-0000-0000-0000-000000000001", 7, None])
def test_recusa_id_que_nao_e_uuid_e_nao_grava_nada(cena: SimpleNamespace, ruim: Any) -> None:
    """Até um texto com cara de UUID é recusado: a forma é do chamador, não do serviço."""
    with pytest.raises(services.InvalidItemId):
        services.create_offer(cena.ana, cena.bruno, [ruim], [cena.b1.id])

    _nada_foi_criado()


@pytest.fixture
def teto_de_duas_pendentes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teto de 2 pendentes por proponente, para o teste não precisar de 40 itens e 20 ofertas."""
    monkeypatch.setattr(rules, "MAX_PENDING_PER_PROPOSER", 2)


def _duas_ofertas_e_uma_a_mais(cena: SimpleNamespace, skin: Any) -> tuple[Any, Any]:
    """ana enche o teto com 2 ofertas; a 3a é recusada. Devolve as duas e deixa a 3a pronta."""
    primeira = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])
    segunda = _oferecer(cena.ana, cena.bruno, [cena.a2], [cena.b2])
    with pytest.raises(services.TooManyPendingOffers):
        _oferecer(cena.ana, cena.bruno, _itens(cena.ana, skin, 1), _itens(cena.bruno, skin, 1))
    assert TradeOffer.objects.count() == 2
    return primeira, segunda


@pytest.mark.usefixtures("teto_de_duas_pendentes")
@pytest.mark.parametrize("encerrar", ["recusar", "cancelar", "aceitar"])
def test_o_teto_de_pendentes_so_conta_pendentes_e_encerrar_libera_vaga(
    cena: SimpleNamespace, skin: Any, encerrar: str
) -> None:
    primeira, _ = _duas_ofertas_e_uma_a_mais(cena, skin)
    if encerrar == "recusar":
        services.decline_offer(cena.bruno, primeira.id)
    elif encerrar == "cancelar":
        services.cancel_offer(cena.ana, primeira.id)
    else:
        services.accept_offer(cena.bruno, primeira.id)

    nova = _oferecer(cena.ana, cena.bruno, _itens(cena.ana, skin, 1), _itens(cena.bruno, skin, 1))

    assert nova.status == "pending"
    assert TradeOffer.objects.filter(status="pending").count() == 2


@pytest.mark.usefixtures("teto_de_duas_pendentes")
def test_o_teto_de_pendentes_e_de_quem_propoe(cena: SimpleNamespace, skin: Any) -> None:
    """bruno recebeu 2 pendentes de ana; como proponente ele ainda tem as vagas dele."""
    _duas_ofertas_e_uma_a_mais(cena, skin)
    dar, pedir = _itens(cena.bruno, skin, 1), _itens(cena.ana, skin, 1)

    de_volta = _oferecer(cena.bruno, cena.ana, dar, pedir)

    assert de_volta.status == "pending"


# --- aceitar -----------------------------------------------------------------------------------


def test_aceitar_troca_os_donos_dos_dois_lados_preservando_id_e_float(
    cena: SimpleNamespace,
) -> None:
    ids_antes = set(SkinInstance.objects.values_list("pk", flat=True))
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1, cena.a2], [cena.b1])

    resultado = services.accept_offer(cena.bruno, oferta.id)

    assert resultado.status == "accepted"
    assert _donos(cena.a1, cena.a2, cena.b1) == [cena.bruno.id, cena.bruno.id, cena.ana.id]
    a1 = SkinInstance.objects.get(pk=cena.a1.pk)
    assert a1.float_value == Decimal("0.123456789")
    assert a1.skin_id == cena.a1.skin_id
    assert SkinInstance.objects.get(pk=cena.b1.pk).float_value == Decimal("0.250000000")
    assert set(SkinInstance.objects.values_list("pk", flat=True)) == ids_antes
    assert len(ids_antes) == 5


def test_aceitar_grava_o_fim_e_libera_as_instancias(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    services.accept_offer(cena.bruno, oferta.id)

    oferta.refresh_from_db()
    assert oferta.status == "accepted"
    assert oferta.resolved_at is not None
    assert [i.active for i in oferta.items.all()] == [False, False]
    assert selectors.busy_instance_ids([cena.a1.id, cena.b1.id]) == set()


def test_aceitar_nao_mexe_nos_itens_de_fora_da_oferta(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    services.accept_offer(cena.bruno, oferta.id)

    assert _donos(cena.a2, cena.b2, cena.c1) == [cena.ana.id, cena.bruno.id, cena.carla.id]


def test_o_item_recebido_pode_ser_oferecido_de_novo_pelo_novo_dono(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])
    services.accept_offer(cena.bruno, oferta.id)
    tornar_amigos(cena.carla, cena.bruno)

    nova = _oferecer(cena.bruno, cena.carla, [cena.a1], [cena.c1])

    assert nova.status == "pending"


def test_so_o_destinatario_aceita(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    with pytest.raises(services.NotAllowed):
        services.accept_offer(cena.ana, oferta.id)

    oferta.refresh_from_db()
    assert oferta.status == "pending"
    assert _donos(cena.a1, cena.b1) == [cena.ana.id, cena.bruno.id]


def test_quem_nao_faz_parte_da_oferta_nao_a_encontra(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    for acao in (services.accept_offer, services.decline_offer, services.cancel_offer):
        with pytest.raises(services.OfferNotFound):
            acao(cena.carla, oferta.id)

    with pytest.raises(services.OfferNotFound):
        services.accept_offer(cena.bruno, uuid.uuid4())
    oferta.refresh_from_db()
    assert oferta.status == "pending"


def test_aceite_depois_de_desfeita_a_amizade_e_recusado_e_nada_muda_de_dono(
    cena: SimpleNamespace,
) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1, cena.a2], [cena.b1])
    Friendship.objects.all().delete()

    with pytest.raises(services.NotFriends):
        services.accept_offer(cena.bruno, oferta.id)

    assert _donos(cena.a1, cena.a2, cena.b1) == [cena.ana.id, cena.ana.id, cena.bruno.id]
    oferta.refresh_from_db()
    assert oferta.status == "pending"
    assert oferta.resolved_at is None


def test_aceite_depois_de_bloqueio_e_recusado(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])
    Friendship.objects.update(requester=cena.bruno, addressee=cena.ana, status="blocked")

    with pytest.raises(services.NotFriends):
        services.accept_offer(cena.bruno, oferta.id)

    assert _donos(cena.a1, cena.b1) == [cena.ana.id, cena.bruno.id]


@pytest.mark.parametrize("quem_mudou", ["oferecido", "pedido"])
def test_aceite_depois_de_uma_instancia_mudar_de_dono_e_recusado(
    cena: SimpleNamespace, quem_mudou: str
) -> None:
    """a1 (de ana) ou b2 (de bruno) vai para carla antes do aceite; a troca inteira é recusada.

    O `change_owner` já recusa mover item em oferta pendente (`ItemLocked`, I-6), então o item é
    movido por fora da porta, direto no ORM: o que se prova aqui é que o aceite revalida o dono
    mesmo assim (defesa em profundidade contra admin, shell ou bug).
    """
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1, cena.a2], [cena.b1, cena.b2])
    item = cena.a1 if quem_mudou == "oferecido" else cena.b2
    SkinInstance.objects.filter(pk=item.pk).update(owner=cena.carla)
    antes = _donos(cena.a1, cena.a2, cena.b1, cena.b2)

    with pytest.raises(services.ItemNotOwned):
        services.accept_offer(cena.bruno, oferta.id)

    assert _donos(cena.a1, cena.a2, cena.b1, cena.b2) == antes
    oferta.refresh_from_db()
    assert oferta.status == "pending"


def test_aceite_com_instancia_consumida_no_meio_e_recusado_sem_mover_nada(
    cena: SimpleNamespace,
) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1, cena.a2], [cena.b1])
    SkinInstance.objects.filter(pk=cena.a2.pk).update(consumed_at=datetime.now(UTC))

    with pytest.raises(services.ItemConsumed):
        services.accept_offer(cena.bruno, oferta.id)

    assert _donos(cena.a1, cena.a2, cena.b1) == [cena.ana.id, cena.ana.id, cena.bruno.id]


# --- recusar e cancelar ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("acao", "ator", "estado"),
    [
        (services.decline_offer, "bruno", "declined"),
        (services.cancel_offer, "ana", "cancelled"),
    ],
)
def test_recusar_e_cancelar_liberam_as_instancias_e_nao_movem_nada(
    cena: SimpleNamespace, acao: Any, ator: str, estado: str
) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    resultado = acao(getattr(cena, ator), oferta.id)

    assert resultado.status == estado
    oferta.refresh_from_db()
    assert oferta.status == estado
    assert oferta.resolved_at is not None
    assert [i.active for i in oferta.items.all()] == [False, False]
    assert _donos(cena.a1, cena.b1) == [cena.ana.id, cena.bruno.id]
    # liberadas: a1 e b1 entram numa oferta nova, sem ItemAlreadyOffered
    nova = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1, cena.b2])
    assert nova.status == "pending"


def test_so_o_destinatario_recusa_e_so_o_proponente_cancela(cena: SimpleNamespace) -> None:
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])

    with pytest.raises(services.NotAllowed):
        services.decline_offer(cena.ana, oferta.id)
    with pytest.raises(services.NotAllowed):
        services.cancel_offer(cena.bruno, oferta.id)

    oferta.refresh_from_db()
    assert oferta.status == "pending"
    assert [i.active for i in oferta.items.all()] == [True, True]


@pytest.mark.parametrize("primeira", ["accept", "decline", "cancel"])
@pytest.mark.parametrize("segunda", ["accept", "decline", "cancel"])
def test_estados_terminais_nao_mudam(cena: SimpleNamespace, primeira: str, segunda: str) -> None:
    acoes = {
        "accept": (services.accept_offer, cena.bruno, "accepted"),
        "decline": (services.decline_offer, cena.bruno, "declined"),
        "cancel": (services.cancel_offer, cena.ana, "cancelled"),
    }
    oferta = _oferecer(cena.ana, cena.bruno, [cena.a1], [cena.b1])
    funcao, ator, estado = acoes[primeira]
    funcao(ator, oferta.id)
    donos = _donos(cena.a1, cena.b1)
    fim = TradeOffer.objects.get(pk=oferta.pk).resolved_at

    funcao_2, ator_2, _ = acoes[segunda]
    with pytest.raises(services.OfferNotPending):
        funcao_2(ator_2, oferta.id)

    oferta.refresh_from_db()
    assert oferta.status == estado
    assert oferta.resolved_at == fim
    assert _donos(cena.a1, cena.b1) == donos
