"""Concorrência do resgate de convites contra Postgres real (RISCOS R2)."""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import connection

from apps.rooms import services
from apps.rooms.models import Room, RoomInvite, RoomMember

from .conftest import criar_usuario

N = 6


def _largar(usuarios: list[Any], codigo: str) -> list[str]:
    """Cada usuário resgata `codigo` no mesmo instante; devolve "ok" ou o `code` do erro."""
    largada = threading.Barrier(len(usuarios))

    def tentar(usuario: Any) -> str:
        try:
            largada.wait()
            services.redeem_invite(usuario, codigo)
            return "ok"
        except services.RoomError as erro:
            return erro.code
        finally:
            connection.close()

    with ThreadPoolExecutor(len(usuarios)) as pool:
        return [f.result() for f in [pool.submit(tentar, u) for u in usuarios]]


@pytest.mark.django_db(transaction=True)
def test_convite_de_um_uso_entra_so_um_dos_resgates_simultaneos() -> None:
    dono = criar_usuario("dono_01")
    sala = services.create_room(dono, "Amigos")
    convite, codigo = services.create_invite(dono, sala.id, max_uses=1)
    jogadores = [criar_usuario(f"jogador_{i}") for i in range(N)]

    resultados = _largar(jogadores, codigo)

    assert sorted(resultados) == ["invite_exhausted"] * (N - 1) + ["ok"]
    assert RoomInvite.objects.get(id=convite.id).uses == 1
    assert RoomMember.objects.filter(room=sala).count() == 2  # o dono + um


@pytest.mark.django_db(transaction=True)
def test_sala_com_uma_vaga_aceita_so_um_resgate_simultaneo() -> None:
    dono = criar_usuario("dono_01")
    sala = services.create_room(dono, "Amigos")
    Room.objects.filter(id=sala.id).update(max_members=2)
    _, codigo = services.create_invite(dono, sala.id, max_uses=50)
    jogadores = [criar_usuario(f"jogador_{i}") for i in range(N)]

    resultados = _largar(jogadores, codigo)

    assert sorted(resultados) == ["ok"] + ["room_full"] * (N - 1)
    assert RoomMember.objects.filter(room=sala, status="active").count() == 2


@pytest.mark.django_db(transaction=True)
def test_o_mesmo_jogador_clicando_varias_vezes_entra_uma_vez_e_gasta_um_uso() -> None:
    dono = criar_usuario("dono_01")
    sala = services.create_room(dono, "Amigos")
    convite, codigo = services.create_invite(dono, sala.id, max_uses=5)
    bruno = criar_usuario("bruno_02")

    resultados = _largar([bruno] * N, codigo)

    assert resultados == ["ok"] * N  # clique duplo nunca vira erro
    assert RoomMember.objects.filter(room=sala, user=bruno).count() == 1
    assert RoomInvite.objects.get(id=convite.id).uses == 1


@pytest.mark.django_db(transaction=True)
def test_revogar_e_resgatar_ao_mesmo_tempo_terminam_coerentes() -> None:
    """Ou o resgate vence (entrou, 1 uso) ou a revogação vence (409); nunca entra sem uso."""
    dono = criar_usuario("dono_01")
    sala = services.create_room(dono, "Amigos")
    convite, codigo = services.create_invite(dono, sala.id, max_uses=5)
    bruno = criar_usuario("bruno_02")
    largada = threading.Barrier(2)

    def resgatar() -> str:
        try:
            largada.wait()
            services.redeem_invite(bruno, codigo)
            return "ok"
        except services.RoomError as erro:
            return erro.code
        finally:
            connection.close()

    def revogar() -> None:
        try:
            largada.wait()
            services.revoke_invite(dono, sala.id, convite.id)
        finally:
            connection.close()

    with ThreadPoolExecutor(2) as pool:
        resgate = pool.submit(resgatar)
        pool.submit(revogar).result()
        resultado = resgate.result()

    entrou = RoomMember.objects.filter(room=sala, user=bruno, status="active").exists()
    usos = RoomInvite.objects.get(id=convite.id).uses
    assert RoomInvite.objects.get(id=convite.id).revoked_at is not None
    assert (resultado, entrou, usos) in [("ok", True, 1), ("invite_revoked", False, 0)]
