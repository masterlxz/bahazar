import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class WalletKind(models.TextChoices):
    PLAYER = "player", "Jogador"
    SYSTEM = "system", "Sistema"


class TransactionKind(models.TextChoices):
    STARTING_GRANT = "starting_grant", "Saldo inicial"
    DAILY_REWARD = "daily_reward", "Recompensa diária"
    AD_REWARD = "ad_reward", "Recompensa por anúncio"
    TRANSFER = "transfer", "Transferência"
    TRADE = "trade", "Troca"
    MARKET_SALE = "market_sale", "Venda no mercado"
    MARKET_PURCHASE = "market_purchase", "Compra no mercado"
    MARKET_FEE = "market_fee", "Taxa do mercado"
    CASE_OPEN = "case_open", "Abertura de caixa"
    CASE_REWARD = "case_reward", "Prêmio de caixa"
    TRADEUP = "tradeup", "Trade-up"
    QUEST_REWARD = "quest_reward", "Recompensa de missão"
    ADJUSTMENT = "adjustment", "Ajuste"


class Wallet(models.Model):
    """Carteira global (ADR 0010): uma por jogador e UMA `system` para o jogo inteiro.

    `balance` é cache do ledger: só `services.post_entries` o altera, na mesma transação
    do lançamento. Em centavos de USD (ADR 0011).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wallet",
    )
    kind = models.CharField(max_length=10, choices=WalletKind.choices)
    balance = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=WalletKind.values), name="wallet_kind_valid"
            ),
            # Só a `system` pode ficar negativa (é a fonte do dinheiro).
            models.CheckConstraint(
                condition=Q(kind="system") | Q(balance__gte=0), name="wallet_player_balance_gte_0"
            ),
            models.CheckConstraint(
                condition=(Q(kind="player") & Q(user__isnull=False))
                | (Q(kind="system") & Q(user__isnull=True)),
                name="wallet_kind_matches_user",
            ),
            # Uma única `system` no jogo inteiro.
            models.UniqueConstraint(
                fields=["kind"], condition=Q(kind="system"), name="wallet_single_system"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.user_id or 'system'}"


class WalletTransaction(models.Model):
    """Linha do ledger. APPEND-ONLY: um trigger do banco bloqueia UPDATE e DELETE.

    Cada operação gera um grupo (`group_id`) de 2+ linhas cuja soma de `amount` é zero.
    Correção de erro é lançamento compensatório (`adjustment`), nunca edição.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transactions")
    group_id = models.UUIDField()
    amount = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    kind = models.CharField(max_length=20, choices=TransactionKind.choices)
    ref_id = models.UUIDField(null=True, blank=True)
    # Vazio = sem chave. Quando há chave, ela é única por carteira.
    idempotency_key = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name="wallettx_amount_not_zero"),
            models.CheckConstraint(
                condition=Q(kind__in=TransactionKind.values), name="wallettx_kind_valid"
            ),
            models.UniqueConstraint(
                fields=["wallet", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="wallettx_unique_idempotency_key",
            ),
        ]
        indexes = [
            models.Index(fields=["wallet", "-created_at", "id"], name="wallettx_extract_idx"),
            models.Index(fields=["group_id"], name="wallettx_group_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount} ({self.wallet_id})"


class DailyClaim(models.Model):
    """Resgate da diária. `claim_number` cresce de 1 em 1 por jogador: o UNIQUE é a última
    defesa contra dois resgates simultâneos (a primeira é a trava da carteira)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="daily_claims"
    )
    claim_number = models.PositiveIntegerField()
    claimed_at = models.DateTimeField()
    streak_day = models.PositiveIntegerField()
    amount = models.BigIntegerField()
    ledger_group_id = models.UUIDField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "claim_number"], name="dailyclaim_unique_number"
            ),
            models.CheckConstraint(condition=Q(streak_day__gte=1), name="dailyclaim_streak_gte_1"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="dailyclaim_amount_gt_0"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} #{self.claim_number} (dia {self.streak_day})"


class IdempotencyRecord(models.Model):
    """Resposta da primeira execução de uma operação com `Idempotency-Key` (ADR 0014).

    `scope` + `key` identificam a intenção (ex.: `user:<remetente>` + a chave do cliente);
    `request_hash` separa "o mesmo pedido de novo" de "a mesma chave para outra coisa". O registro
    nasce na MESMA transação da operação (`idempotency.run_once`), então nunca existe sem ela.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=80)
    key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "key"], name="idempotency_unique_scope_key"),
        ]

    def __str__(self) -> str:
        return f"{self.scope} {self.key}"
