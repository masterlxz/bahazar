import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { formatUsd } from "../../lib/money";
import { ApiError } from "../../services/http";
import { claimDaily } from "../../services/wallet";
import type { Wallet } from "../../types/api";
import { WALLET_KEY, useWallet } from "./useWallet";

const DAILY_NOT_READY = "daily_not_ready";

function formatarQuando(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function DailyCard({ daily }: { daily: Wallet["daily"] }) {
  const queryClient = useQueryClient();
  const resgatar = useMutation({
    mutationFn: claimDaily,
    // O estado novo (saldo, quando libera) vem do servidor, não de conta feita aqui.
    onSettled: () => queryClient.invalidateQueries({ queryKey: WALLET_KEY }),
  });

  const naoLiberada = resgatar.error instanceof ApiError && resgatar.error.code === DAILY_NOT_READY;

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Diária
      </h2>
      <p className="text-sm text-muted-foreground">Dia {daily.next_streak_day} da sequência</p>
      <div>
        <Button
          onClick={() => resgatar.mutate()}
          disabled={!daily.can_claim || resgatar.isPending}
        >
          {resgatar.isPending ? "Resgatando…" : `Resgatar ${formatUsd(daily.next_amount)}`}
        </Button>
      </div>
      {!daily.can_claim && daily.available_at && (
        <p className="text-sm text-muted-foreground">
          Disponível a partir de {formatarQuando(daily.available_at)}
        </p>
      )}
      {resgatar.data && (
        <p role="status" className="text-sm">
          Você recebeu {formatUsd(resgatar.data.amount)} (dia {resgatar.data.streak_day})
        </p>
      )}
      {resgatar.isError && (
        <p role="alert" className="text-sm text-primary">
          {naoLiberada
            ? "Ainda não está disponível. Tente de novo mais tarde."
            : "Não foi possível resgatar a diária. Tente novamente."}
        </p>
      )}
    </section>
  );
}

export default function WalletPage() {
  const wallet = useWallet();

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Sua carteira</h1>

      {wallet.isError && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar a carteira. Tente novamente.
        </p>
      )}

      {wallet.data && (
        <>
          <section className="flex flex-col gap-1 rounded-lg border border-border bg-card p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Saldo
            </h2>
            <p data-testid="saldo" className="text-3xl font-bold tracking-tight">
              {formatUsd(wallet.data.balance)}
            </p>
          </section>
          <DailyCard daily={wallet.data.daily} />
        </>
      )}
    </main>
  );
}
