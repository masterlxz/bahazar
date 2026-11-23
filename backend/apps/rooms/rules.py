"""Regras puras de salas: sem Django e sem I/O, testáveis sem banco."""

from datetime import datetime

MAX_ROOMS_AS_OWNER = 5


def can_create_room(owned_active_rooms: int) -> bool:
    """Limite anti-abuso: no máximo `MAX_ROOMS_AS_OWNER` salas ativas como dono."""
    return owned_active_rooms < MAX_ROOMS_AS_OWNER


def can_leave(role: str) -> bool:
    """O dono não sai: uma sala nunca fica sem dono."""
    return role != "owner"


def is_room_admin(role: str | None) -> bool:
    return role in ("owner", "admin")


# --- convites (SEGURANCA §5) ---

DEFAULT_INVITE_DAYS = 7
DEFAULT_INVITE_USES = 10
MAX_INVITE_DAYS = 30
MAX_INVITE_USES = 50
MAX_ACTIVE_INVITES = 10


def invite_policy_valid(days: int, uses: int) -> bool:
    """Validade e usos dentro dos tetos. Acima do teto é recusado, nunca "corrigido"."""
    return 1 <= days <= MAX_INVITE_DAYS and 1 <= uses <= MAX_INVITE_USES


def invite_state(
    *, now: datetime, expires_at: datetime, revoked: bool, uses: int, max_uses: int
) -> str:
    """`ok`, `revoked`, `expired` ou `exhausted`, nesta ordem de precedência.

    `expires_at` é o primeiro instante em que o convite NÃO vale mais.
    """
    if revoked:
        return "revoked"
    if now > expires_at:
        return "expired"
    if uses >= max_uses:
        return "exhausted"
    return "ok"


def room_is_full(active_members: int, max_members: int) -> bool:
    return active_members >= max_members
