"""Avatares pré-definidos: o jogador escolhe uma chave desta lista (nunca uma URL livre).

Os desenhos reais ficam para a etapa visual; aqui só as chaves estáveis.
"""

DEFAULT_AVATAR = "default"

AVATAR_KEYS = (
    DEFAULT_AVATAR,
    "ember",
    "glacier",
    "verdant",
    "violet",
    "amber",
    "slate",
    "crimson",
)

AVATAR_CHOICES = [(chave, chave) for chave in AVATAR_KEYS]
