"""Gancho "o par acabou" de `friends` (`apps.friends.hooks`).

`friends` não importa `trades` (trades já importa friends; seria ciclo): quem precisa reagir ao
fim de um par registra uma função, no padrão de `inventory.services.register_move_guard`. Só
bloquear e desfazer a amizade avisam; o efeito sobre as ofertas está em
`tests/trades/test_trades_par_encerrado.py`.

O módulo é lido por `importlib` só porque este arquivo nasce antes dele: sem isso o import
quebraria a coleta de TODOS os testes.
"""

import importlib
from typing import Any

import pytest

from apps.friends import services
from apps.friends.models import Friendship

pytestmark = pytest.mark.django_db


@pytest.fixture
def hooks(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O módulo, com a lista de ganchos esvaziada: só os espiões do teste ficam registrados."""
    modulo = importlib.import_module("apps.friends.hooks")
    monkeypatch.setattr(modulo, "_PAIR_ENDED_HOOKS", [])
    return modulo


@pytest.fixture
def chamadas(hooks: Any) -> list[tuple[Any, Any, int, str | None]]:
    """Registra um espião que anota `(a, b, linhas de amizade, estado da relação)` ao ser chamado.

    O estado é lido DENTRO da chamada: prova que o aviso vem depois de gravar a mudança.
    """
    anotadas: list[tuple[Any, Any, int, str | None]] = []

    def espiao(a: Any, b: Any) -> None:
        relacao = Friendship.objects.first()
        anotadas.append(
            (a.pk, b.pk, Friendship.objects.count(), relacao.status if relacao else None)
        )

    hooks.register_pair_ended_hook(espiao)
    return anotadas


def test_notifica_na_ordem_do_registro_e_registrar_de_novo_nao_duplica(
    hooks: Any, ana: Any, bruno: Any
) -> None:
    vistas: list[str] = []

    def primeiro(a: Any, b: Any) -> None:
        vistas.append("primeiro")

    def segundo(a: Any, b: Any) -> None:
        vistas.append("segundo")

    for gancho in (primeiro, segundo, primeiro):
        hooks.register_pair_ended_hook(gancho)

    hooks.notify_pair_ended(ana, bruno)

    assert vistas == ["primeiro", "segundo"]


def test_bloquear_avisa_uma_vez_com_o_par_na_ordem_de_quem_bloqueia_depois_de_gravar(
    chamadas: list[tuple[Any, Any, int, str | None]], ana: Any, bruno: Any
) -> None:
    services.block(bruno, ana.username)

    assert chamadas == [(bruno.pk, ana.pk, 1, "blocked")]


def test_desfazer_a_amizade_avisa_uma_vez_depois_de_apagar_a_linha(
    chamadas: list[tuple[Any, Any, int, str | None]], ana: Any, bruno: Any
) -> None:
    pedido = services.send_request(ana, bruno.username)
    services.accept_request(bruno, pedido.id)

    services.remove_friend(bruno, ana.username)

    assert chamadas == [(bruno.pk, ana.pk, 0, None)]


def test_pedir_aceitar_e_recusar_nao_avisam(
    chamadas: list[tuple[Any, Any, int, str | None]], ana: Any, bruno: Any, carla: Any
) -> None:
    recusado = services.send_request(ana, carla.username)
    services.decline_request(carla, recusado.id)
    aceito = services.send_request(ana, bruno.username)
    services.accept_request(bruno, aceito.id)

    assert chamadas == []


def test_desbloquear_nao_avisa(
    chamadas: list[tuple[Any, Any, int, str | None]], ana: Any, bruno: Any
) -> None:
    services.block(ana, bruno.username)
    assert len(chamadas) == 1

    services.unblock(ana, bruno.username)

    assert len(chamadas) == 1  # só o bloqueio avisou


def test_operacao_que_falha_nao_avisa(
    chamadas: list[tuple[Any, Any, int, str | None]], ana: Any, bruno: Any
) -> None:
    with pytest.raises(services.NotFound):
        services.block(ana, "ninguem_99")
    with pytest.raises(services.NotFound):
        services.remove_friend(ana, bruno.username)  # não são amigos
    with pytest.raises(services.NotFound):
        services.unblock(ana, bruno.username)

    assert chamadas == []


def test_gancho_que_levanta_desfaz_o_bloqueio_porque_roda_dentro_da_transacao(
    hooks: Any, ana: Any, bruno: Any
) -> None:
    def falha(a: Any, b: Any) -> None:
        raise RuntimeError("gancho quebrado")

    hooks.register_pair_ended_hook(falha)

    with pytest.raises(RuntimeError, match="gancho quebrado"):
        services.block(ana, bruno.username)

    assert Friendship.objects.count() == 0
