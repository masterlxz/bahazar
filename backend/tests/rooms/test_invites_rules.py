"""Regras puras de convite: sem banco. Os limites são decisão do dono (SEGURANCA §5)."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.rooms import rules

T0 = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)


def test_padrao_e_sete_dias_e_dez_usos_com_tetos_de_trinta_e_cinquenta() -> None:
    assert rules.DEFAULT_INVITE_DAYS == 7
    assert rules.DEFAULT_INVITE_USES == 10
    assert rules.MAX_INVITE_DAYS == 30
    assert rules.MAX_INVITE_USES == 50
    assert rules.MAX_ACTIVE_INVITES == 10


@pytest.mark.parametrize(
    ("dias", "usos", "valido"),
    [
        (1, 1, True),
        (7, 10, True),
        (30, 50, True),  # os tetos valem
        (31, 10, False),
        (7, 51, False),
        (0, 10, False),
        (7, 0, False),
        (-1, 10, False),
        (7, -5, False),
    ],
)
def test_politica_do_convite(dias: int, usos: int, valido: bool) -> None:
    assert rules.invite_policy_valid(dias, usos) is valido


def test_convite_dentro_do_prazo_e_com_usos_esta_ok() -> None:
    estado = rules.invite_state(
        now=T0, expires_at=T0 + timedelta(days=1), revoked=False, uses=9, max_uses=10
    )
    assert estado == "ok"


def test_no_instante_exato_da_expiracao_o_convite_ja_expirou() -> None:
    """Borda: `expires_at` é o primeiro instante em que NÃO vale mais."""
    antes = rules.invite_state(
        now=T0 - timedelta(seconds=1), expires_at=T0, revoked=False, uses=0, max_uses=10
    )
    no_instante = rules.invite_state(now=T0, expires_at=T0, revoked=False, uses=0, max_uses=10)

    assert antes == "ok"
    assert no_instante == "expired"


def test_convite_esgota_quando_os_usos_chegam_ao_maximo() -> None:
    nove = rules.invite_state(
        now=T0, expires_at=T0 + timedelta(days=1), revoked=False, uses=9, max_uses=10
    )
    dez = rules.invite_state(
        now=T0, expires_at=T0 + timedelta(days=1), revoked=False, uses=10, max_uses=10
    )

    assert (nove, dez) == ("ok", "exhausted")


def test_revogado_vence_expirado_e_esgotado() -> None:
    estado = rules.invite_state(
        now=T0, expires_at=T0 - timedelta(days=1), revoked=True, uses=10, max_uses=10
    )
    assert estado == "revoked"


def test_expirado_vence_esgotado() -> None:
    estado = rules.invite_state(
        now=T0, expires_at=T0 - timedelta(days=1), revoked=False, uses=10, max_uses=10
    )
    assert estado == "expired"


@pytest.mark.parametrize(
    ("ativos", "maximo", "cheia"),
    [(19, 20, False), (20, 20, True), (21, 20, True), (1, 1, True), (0, 1, False)],
)
def test_sala_cheia(ativos: int, maximo: int, cheia: bool) -> None:
    assert rules.room_is_full(ativos, maximo) is cheia
