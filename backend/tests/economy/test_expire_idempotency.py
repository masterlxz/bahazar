"""`expire_idempotency`: apaga só os registros de idempotência ANTERIORES ao corte (ADR 0014).

O relógio do comando é fixado em T0 (`idempotency_expiry._now`). O corte é `T0 - N dias` e só
apaga o que é ESTRITAMENTE anterior a ele.
"""

import uuid
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from pytest import MonkeyPatch

from apps.economy import audit, idempotency, idempotency_expiry, services
from apps.economy.idempotency_expiry import MAX_DAYS
from apps.economy.models import IdempotencyRecord, Wallet, WalletTransaction

from .conftest import T0

pytestmark = pytest.mark.django_db

HASH = "a" * 64
DIA = timedelta(days=1)


@pytest.fixture(autouse=True)
def relogio_parado(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(idempotency_expiry, "_now", lambda: T0)


def _registro(idade: timedelta, scope: str = "user:a", key: str = "") -> IdempotencyRecord:
    """Registro criado `idade` antes de T0 (o `created_at` é gravado direto, sem esperar)."""
    return IdempotencyRecord.objects.create(
        scope=scope, key=key or str(uuid.uuid4()), request_hash=HASH, created_at=T0 - idade
    )


def _expirar(*args: str) -> str:
    saida = StringIO()
    call_command("expire_idempotency", *args, stdout=saida)
    return saida.getvalue()


def _ids() -> set[Any]:
    return set(IdempotencyRecord.objects.values_list("pk", flat=True))


def _ledger() -> list[Any]:
    return sorted(WalletTransaction.objects.values_list("pk", "wallet_id", "amount", "kind"))


def _saldos() -> list[Any]:
    return sorted(Wallet.objects.values_list("pk", "balance"))


def test_apaga_os_mais_velhos_que_o_corte_e_mantem_o_mais_novo() -> None:
    _registro(5 * DIA)
    _registro(3 * DIA)
    novo = _registro(1 * DIA)

    saida = _expirar("--days", "2")

    assert _ids() == {novo.pk}
    assert "Apagados 2 registro(s) de idempotência com mais de 2 dia(s)" in saida


def test_registro_exatamente_no_corte_e_mantido() -> None:
    no_corte = _registro(2 * DIA)  # created_at == T0 - 2 dias: NÃO é anterior ao corte
    _registro(2 * DIA + timedelta(microseconds=1))  # um instante antes do corte: apaga

    _expirar("--days", "2")

    assert _ids() == {no_corte.pk}


def test_dry_run_so_conta_e_nao_apaga() -> None:
    _registro(5 * DIA)
    _registro(4 * DIA)
    _registro(3 * DIA)
    _registro(1 * DIA)
    antes = _ids()

    saida = _expirar("--days", "2", "--dry-run")

    assert _ids() == antes
    assert "Dry-run" in saida
    assert "3 registro(s) de idempotência com mais de 2 dia(s)" in saida
    assert "Nada foi apagado" in saida


@pytest.mark.parametrize("dias", ["0", "-3", str(MAX_DAYS + 1), str(10**9)])
def test_days_fora_de_1_a_max_e_recusado_e_nao_apaga_nada(dias: str) -> None:
    _registro(30 * DIA)
    _registro(1 * DIA)
    antes = _ids()

    with pytest.raises(CommandError, match="--days"):
        _expirar("--days", dias)

    assert _ids() == antes


def test_sem_argumento_a_retencao_padrao_e_de_7_dias() -> None:
    _registro(8 * DIA)
    no_corte = _registro(7 * DIA)
    seis = _registro(6 * DIA)

    saida = _expirar()

    assert _ids() == {no_corte.pk, seis.pk}
    assert "Apagados 1 registro(s) de idempotência com mais de 7 dia(s)" in saida


def test_days_1_e_o_piso_aceito_apaga_acima_de_1_dia_e_mantem_o_de_exatamente_1() -> None:
    no_corte = _registro(1 * DIA)  # created_at == T0 - 1 dia: mantido
    _registro(1 * DIA + timedelta(microseconds=1))

    saida = _expirar("--days", "1")

    assert _ids() == {no_corte.pk}
    assert "Apagados 1 registro(s) de idempotência com mais de 1 dia(s)" in saida


def test_days_no_teto_e_aceito_sem_estourar() -> None:
    recente = _registro(1 * DIA)
    _registro((MAX_DAYS + 1) * DIA)  # um dia além do teto: expira

    saida = _expirar("--days", str(MAX_DAYS))

    assert _ids() == {recente.pk}
    assert f"com mais de {MAX_DAYS} dia(s)" in saida


def test_apagar_nao_toca_no_ledger_nem_nas_carteiras(ana: Any, bruno: Any) -> None:
    services.transfer(ana, bruno, 1_000, idempotency_key=str(uuid.uuid4()))
    IdempotencyRecord.objects.update(created_at=T0 - 30 * DIA)
    ledger, saldos = _ledger(), _saldos()
    assert IdempotencyRecord.objects.count() == 1
    assert len(ledger) > 0

    _expirar("--days", "7")

    assert IdempotencyRecord.objects.count() == 0
    assert (_ledger(), _saldos()) == (ledger, saldos)
    assert audit.check_ledger() == []


def test_rodar_duas_vezes_e_seguro() -> None:
    _registro(5 * DIA)
    novo = _registro(1 * DIA)

    primeira = _expirar("--days", "2")
    segunda = _expirar("--days", "2")

    assert "Apagados 1 registro(s)" in primeira
    assert "Apagados 0 registro(s)" in segunda
    assert _ids() == {novo.pk}


def test_escopos_diferentes_expiram_do_mesmo_jeito() -> None:
    chave = str(uuid.uuid4())
    _registro(5 * DIA, scope="user:a", key=chave)
    _registro(5 * DIA, scope="user:b", key=chave)  # mesma chave, outro escopo
    _registro(4 * DIA, scope="trade:xyz")
    novos = {_registro(1 * DIA, scope=s).pk for s in ("user:a", "user:b", "trade:xyz")}

    _expirar("--days", "2")

    assert _ids() == novos


def test_chave_expirada_pode_ser_reutilizada_e_executa_de_novo() -> None:
    """O RISCO da janela, fixado como comportamento: depois de expirar, a chave vale outra vez."""
    chamadas: list[int] = []

    def operar() -> tuple[int, dict[str, Any]]:
        chamadas.append(1)
        return 201, {"n": len(chamadas)}

    chave = str(uuid.uuid4())
    kwargs: dict[str, Any] = {"scope": "user:a", "key": chave, "request_hash": HASH}
    idempotency.run_once(operation=operar, **kwargs)
    IdempotencyRecord.objects.update(created_at=T0 - 30 * DIA)

    _expirar("--days", "7")
    de_novo = idempotency.run_once(operation=operar, **kwargs)

    assert (de_novo.replayed, chamadas) == (False, [1, 1])


def test_funcao_usa_o_now_recebido_e_devolve_a_contagem() -> None:
    _registro(0 * DIA)  # created_at == T0

    contados = idempotency_expiry.expire_records(days=7, now=T0 + 10 * DIA, dry_run=True)
    assert (contados, IdempotencyRecord.objects.count()) == (1, 1)

    apagados = idempotency_expiry.expire_records(days=7, now=T0 + 10 * DIA)
    assert (apagados, IdempotencyRecord.objects.count()) == (1, 0)


def test_funcao_com_days_1_apaga_acima_de_1_dia_e_mantem_o_de_exatamente_1() -> None:
    no_corte = _registro(1 * DIA)
    _registro(1 * DIA + timedelta(microseconds=1))

    apagados = idempotency_expiry.expire_records(days=1, now=T0)

    assert (apagados, _ids()) == (1, {no_corte.pk})


def test_funcao_com_days_no_teto_aceita_e_nao_estoura() -> None:
    recente = _registro(1 * DIA)
    _registro((MAX_DAYS + 1) * DIA)

    apagados = idempotency_expiry.expire_records(days=MAX_DAYS, now=T0)

    assert (apagados, _ids()) == (1, {recente.pk})


@pytest.mark.parametrize("dias", [0, -1, MAX_DAYS + 1, 10**9])
def test_funcao_recusa_days_fora_de_1_a_max_e_nao_apaga(dias: int) -> None:
    _registro(30 * DIA)

    with pytest.raises(ValueError, match="days"):
        idempotency_expiry.expire_records(days=dias, now=T0)

    assert IdempotencyRecord.objects.count() == 1


def test_transferencia_repetida_depois_de_expirar_nao_move_dinheiro_de_novo(
    ana: Any, bruno: Any
) -> None:
    """A defesa real contra a dupla gravação é o UNIQUE do ledger, não o registro de idempotência.

    Depois de expirar o registro, o mesmo `transfer` (mesma chave, mesmo pedido) executa a
    operação de novo, mas o `UNIQUE(wallet, idempotency_key)` do ledger recusa a segunda
    gravação. Este teste cai se `post_entries` deixar de gravar a chave no ledger
    (`idempotency_key=...` em `transfer`) ou se a restrição `wallettx_unique_idempotency_key`
    sair do banco (migração).
    """
    chave = str(uuid.uuid4())
    services.transfer(ana, bruno, 1_000, idempotency_key=chave)
    ledger, saldos = _ledger(), _saldos()
    IdempotencyRecord.objects.update(created_at=T0 - 30 * DIA)

    assert idempotency_expiry.expire_records(days=7, now=T0) == 1
    with pytest.raises(IntegrityError, match="wallettx_unique_idempotency_key"):
        services.transfer(ana, bruno, 1_000, idempotency_key=chave)

    assert (_ledger(), _saldos()) == (ledger, saldos)
    # o registro novo foi desfeito junto com a operação
    assert IdempotencyRecord.objects.count() == 0
    assert audit.check_ledger() == []
