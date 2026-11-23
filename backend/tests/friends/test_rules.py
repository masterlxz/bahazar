"""Regras puras de amizade: sem banco. A decisão de "o que fazer com um pedido novo"."""

import pytest

from apps.friends import rules


def test_sem_relacao_previa_o_pedido_e_criado() -> None:
    assert rules.request_outcome(None) == "create"


@pytest.mark.parametrize(
    ("status", "pedido_foi_meu", "esperado"),
    [
        ("pending", True, "already_pending"),  # cliquei duas vezes
        ("pending", False, "already_pending"),  # ele já me pediu: aceite o dele, não crio outro
        ("accepted", True, "already_friends"),
        ("accepted", False, "already_friends"),
        ("blocked", True, "unavailable"),  # eu bloqueei: desbloqueie antes
        ("blocked", False, "unavailable"),  # ele me bloqueou: não revelo o motivo
    ],
)
def test_pedido_sobre_relacao_existente(status: str, pedido_foi_meu: bool, esperado: str) -> None:
    assert rules.request_outcome((status, pedido_foi_meu)) == esperado


def test_o_bloqueado_nao_se_distingue_de_um_alvo_inexistente() -> None:
    """Quem foi bloqueado recebe o mesmo código de quem não pode pedir por outro motivo."""
    assert rules.request_outcome(("blocked", False)) == rules.UNAVAILABLE


def test_dono_ve_a_si_mesmo_e_amigo_aceito_ve() -> None:
    assert rules.can_view(same_user=True, friendship_status=None) is True
    assert rules.can_view(same_user=False, friendship_status="accepted") is True


@pytest.mark.parametrize("status", [None, "pending", "blocked", "qualquer_outro"])
def test_ninguem_mais_ve(status: str | None) -> None:
    assert rules.can_view(same_user=False, friendship_status=status) is False
