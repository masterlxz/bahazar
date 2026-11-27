"""Regras puras da troca (`apps.trades.rules`): sem banco, sem Django."""

import uuid

import pytest

from apps.trades import rules

ANA = uuid.UUID(int=1)
BRUNO = uuid.UUID(int=2)
CARLA = uuid.UUID(int=3)
X, Y, Z = (uuid.UUID(int=n) for n in (10, 11, 12))


# --- forma da oferta ---------------------------------------------------------------------------


def test_oferta_bem_formada_nao_tem_problema() -> None:
    assert rules.offer_shape_problem(ANA, BRUNO, [X, Y], [Z]) is None


def test_ninguem_troca_com_si_mesmo() -> None:
    assert rules.offer_shape_problem(ANA, ANA, [X], [Y]) == rules.SELF_TRADE


@pytest.mark.parametrize(("oferecidos", "pedidos"), [([], [X]), ([X], []), ([], [])])
def test_cada_lado_precisa_de_pelo_menos_um_item(
    oferecidos: list[uuid.UUID], pedidos: list[uuid.UUID]
) -> None:
    assert rules.offer_shape_problem(ANA, BRUNO, oferecidos, pedidos) == rules.EMPTY_SIDE


@pytest.mark.parametrize(
    ("oferecidos", "pedidos"),
    [([X, X], [Y]), ([X], [Y, Y]), ([X, Y], [Z, X])],
    ids=["repetido no lado oferecido", "repetido no lado pedido", "o mesmo item nos dois lados"],
)
def test_o_mesmo_item_nao_aparece_duas_vezes(
    oferecidos: list[uuid.UUID], pedidos: list[uuid.UUID]
) -> None:
    assert rules.offer_shape_problem(ANA, BRUNO, oferecidos, pedidos) == rules.DUPLICATE_ITEM


def test_auto_troca_vence_lado_vazio_na_ordem_de_checagem() -> None:
    """A ordem é parte do contrato: o erro mais básico (quem troca) vem antes dos itens."""
    assert rules.offer_shape_problem(ANA, ANA, [], []) == rules.SELF_TRADE


# --- estado de cada item -----------------------------------------------------------------------


def test_item_do_dono_esperado_e_em_jogo_nao_tem_problema() -> None:
    problema = rules.item_problem(expected_owner_id=ANA, actual_owner_id=ANA, consumed=False)

    assert problema is None


def test_item_de_outro_dono_e_recusado() -> None:
    problema = rules.item_problem(expected_owner_id=ANA, actual_owner_id=CARLA, consumed=False)

    assert problema == rules.NOT_OWNER


def test_item_inexistente_conta_como_de_outro_dono() -> None:
    problema = rules.item_problem(expected_owner_id=ANA, actual_owner_id=None, consumed=False)

    assert problema == rules.NOT_OWNER


def test_item_consumido_do_dono_certo_e_recusado() -> None:
    problema = rules.item_problem(expected_owner_id=ANA, actual_owner_id=ANA, consumed=True)

    assert problema == rules.CONSUMED


def test_o_dono_errado_vence_o_consumido() -> None:
    problema = rules.item_problem(expected_owner_id=ANA, actual_owner_id=CARLA, consumed=True)

    assert problema == rules.NOT_OWNER


# --- quem pode fazer o quê, e o estado seguinte -------------------------------------------------


@pytest.mark.parametrize(
    ("acao", "ator", "pode"),
    [
        (rules.ACCEPT, BRUNO, True),
        (rules.ACCEPT, ANA, False),
        (rules.ACCEPT, CARLA, False),
        (rules.DECLINE, BRUNO, True),
        (rules.DECLINE, ANA, False),
        (rules.DECLINE, CARLA, False),
        (rules.CANCEL, ANA, True),
        (rules.CANCEL, BRUNO, False),
        (rules.CANCEL, CARLA, False),
    ],
)
def test_aceitar_e_recusar_sao_do_destinatario_e_cancelar_e_do_proponente(
    acao: str, ator: uuid.UUID, pode: bool
) -> None:
    resultado = rules.may_act(acao, actor_id=ator, proposer_id=ANA, recipient_id=BRUNO)

    assert resultado is pode


def test_acao_desconhecida_nao_e_permitida_a_ninguem() -> None:
    assert rules.may_act("apagar", actor_id=ANA, proposer_id=ANA, recipient_id=BRUNO) is False


@pytest.mark.parametrize(
    ("acao", "estado"),
    [
        (rules.ACCEPT, rules.ACCEPTED),
        (rules.DECLINE, rules.DECLINED),
        (rules.CANCEL, rules.CANCELLED),
        (rules.EXPIRE, rules.EXPIRED),
    ],
)
def test_estado_depois_de_cada_acao(acao: str, estado: str) -> None:
    assert rules.status_after(acao) == estado


@pytest.mark.parametrize(
    ("estado", "pode"),
    [
        (rules.PENDING, True),
        (rules.ACCEPTED, False),
        (rules.DECLINED, False),
        (rules.CANCELLED, False),
        ("qualquer_outro", False),
    ],
)
def test_so_a_oferta_pendente_muda_de_estado(estado: str, pode: bool) -> None:
    assert rules.can_resolve(estado) is pode


# --- tetos: HIPÓTESE do coordenador (20 e 20), sem fonte no projeto -----------------------------


def _ids(quantos: int, *, inicio: int = 1000) -> list[uuid.UUID]:
    return [uuid.UUID(int=inicio + n) for n in range(quantos)]


@pytest.mark.parametrize("lado", ["oferecidos", "pedidos"])
def test_exatamente_no_teto_de_itens_por_lado_passa(lado: str) -> None:
    cheio, um = _ids(rules.MAX_ITEMS_PER_SIDE), _ids(1, inicio=5000)
    oferecidos, pedidos = (cheio, um) if lado == "oferecidos" else (um, cheio)

    assert rules.offer_shape_problem(ANA, BRUNO, oferecidos, pedidos) is None


@pytest.mark.parametrize("lado", ["oferecidos", "pedidos", "ambos"])
def test_um_item_acima_do_teto_por_lado_e_recusado(lado: str) -> None:
    demais = _ids(rules.MAX_ITEMS_PER_SIDE + 1)
    outros = _ids(rules.MAX_ITEMS_PER_SIDE + 1, inicio=5000)
    oferecidos = demais if lado in ("oferecidos", "ambos") else _ids(1, inicio=9000)
    pedidos = outros if lado in ("pedidos", "ambos") else _ids(1, inicio=9500)

    assert rules.offer_shape_problem(ANA, BRUNO, oferecidos, pedidos) == rules.TOO_MANY_ITEMS


def test_o_teto_e_por_lado_e_nao_da_oferta_inteira() -> None:
    """20 de cada lado são 40 itens no total e passam."""
    oferecidos = _ids(rules.MAX_ITEMS_PER_SIDE)
    pedidos = _ids(rules.MAX_ITEMS_PER_SIDE, inicio=5000)

    assert rules.offer_shape_problem(ANA, BRUNO, oferecidos, pedidos) is None


@pytest.mark.parametrize(
    "ruim",
    [str(X), 10, None, X.bytes, X.hex],
    ids=["texto com cara de uuid", "inteiro", "nulo", "bytes", "hex"],
)
@pytest.mark.parametrize("lado", ["oferecidos", "pedidos"])
def test_id_que_nao_e_uuid_e_erro_de_forma(ruim: object, lado: str) -> None:
    oferecidos: list[object] = [X, ruim] if lado == "oferecidos" else [X]
    pedidos: list[object] = [Y, ruim] if lado == "pedidos" else [Y]

    assert rules.offer_shape_problem(ANA, BRUNO, oferecidos, pedidos) == rules.INVALID_ID


def test_id_invalido_vence_a_repeticao_na_ordem_de_checagem() -> None:
    assert rules.offer_shape_problem(ANA, BRUNO, ["a", "a"], [Y]) == rules.INVALID_ID


def test_lado_vazio_vence_id_invalido_na_ordem_de_checagem() -> None:
    assert rules.offer_shape_problem(ANA, BRUNO, [], ["a"]) == rules.EMPTY_SIDE


@pytest.mark.parametrize(
    ("pendentes", "estoura"),
    [
        (0, False),
        (rules.MAX_PENDING_PER_PROPOSER - 1, False),
        (rules.MAX_PENDING_PER_PROPOSER, True),
        (rules.MAX_PENDING_PER_PROPOSER + 1, True),
    ],
    ids=["nenhuma", "uma abaixo do teto", "no teto", "acima do teto"],
)
def test_nova_oferta_so_cabe_abaixo_do_teto_de_pendentes(pendentes: int, estoura: bool) -> None:
    """Quem já tem `MAX` pendentes não abre a próxima: o teto é de pendentes, não de total."""
    assert rules.pending_limit_exceeded(pendentes) is estoura
