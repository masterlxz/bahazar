"""Regras puras de salas: sem Django e sem I/O, testáveis sem banco."""

MAX_ROOMS_AS_OWNER = 5


def can_create_room(owned_active_rooms: int) -> bool:
    """Limite anti-abuso: no máximo `MAX_ROOMS_AS_OWNER` salas ativas como dono."""
    return owned_active_rooms < MAX_ROOMS_AS_OWNER


def can_leave(role: str) -> bool:
    """O dono não sai: uma sala nunca fica sem dono."""
    return role != "owner"


def is_room_admin(role: str | None) -> bool:
    return role in ("owner", "admin", "member")
