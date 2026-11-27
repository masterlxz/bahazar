"""Gancho "o par acabou": quem precisa reagir a um bloqueio ou ao fim de uma amizade se registra.

`friends` não conhece os módulos que dependem dele (`trades` já importa `friends`; o caminho
inverso seria um ciclo, e `tests/friends/test_friends_arquitetura.py` exige `friends` isolado).
Cada módulo registra a sua função em `AppConfig.ready()`, no padrão de
`inventory.services.register_move_guard`; `friends.services` a chama DENTRO da transação de
`block` e `remove_friend`, com os dois jogadores já travados e a mudança já gravada.

Um gancho que levanta exceção desfaz a operação inteira (o bloqueio some junto): por isso ele não
pode falhar em condição normal.
"""

from collections.abc import Callable

from apps.accounts.models import User

PairEndedHook = Callable[[User, User], None]

_PAIR_ENDED_HOOKS: list[PairEndedHook] = []


def register_pair_ended_hook(hook: PairEndedHook) -> None:
    """Registra um gancho (idempotente: a mesma função entra uma só vez)."""
    if hook not in _PAIR_ENDED_HOOKS:
        _PAIR_ENDED_HOOKS.append(hook)


def notify_pair_ended(a: User, b: User) -> None:
    """Avisa, na ordem do registro, que o par `a`/`b` acabou (bloqueio ou amizade desfeita)."""
    for hook in _PAIR_ENDED_HOOKS:
        hook(a, b)
