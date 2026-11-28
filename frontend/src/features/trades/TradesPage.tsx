import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AtribuicaoSkinport } from "../../components/AtribuicaoSkinport";
import { Avatar } from "../../components/ui/avatar";
import { Button } from "../../components/ui/button";
import { ConfirmButton } from "../../components/ui/ConfirmButton";
import { formatUsd } from "../../lib/money";
import { ApiError } from "../../services/http";
import { acceptTrade, cancelTrade, declineTrade } from "../../services/trades";
import type { TradeItem, TradeOffer, TradeStatus } from "../../types/api";
import { useSession } from "../auth/useSession";
import { INVENTORY_ROOT_KEY } from "../inventory/useInventory";
import { TRADES_ROOT_KEY, useTrades } from "./useTrades";

const MUDOU = "Essa oferta mudou. Atualizamos a lista.";
const FALHOU = "Não foi possível concluir a ação. Tente novamente.";
const INDISPONIVEL = "Um dos itens não está mais disponível.";

// Os textos são genéricos de propósito: nenhum diz que uma conta está desativada ou bloqueou
// alguém (ADR 0020 e 0021, SEGURANCA.md). O texto do servidor nunca é mostrado.
const POR_CODIGO: Record<string, string> = {
  offer_not_pending: MUDOU,
  offer_not_found: MUDOU,
  player_unavailable: "Esse jogador não está disponível para esta ação.",
  not_friends: "Vocês não são mais amigos.",
  item_not_owned: INDISPONIVEL,
  item_consumed: INDISPONIVEL,
  item_already_offered: INDISPONIVEL,
};

function mensagemDoErro(erro: unknown): string {
  if (!(erro instanceof ApiError)) return FALHOU;
  const doCodigo = erro.code ? POR_CODIGO[erro.code] : undefined;
  if (doCodigo) return doCodigo;
  if (erro.status === 404) return MUDOU;
  if (erro.status === 429) return "Muitas ações seguidas. Espere um pouco.";
  return FALHOU;
}

const ROTULO: Record<TradeStatus, string> = {
  pending: "Pendente",
  accepted: "Aceita",
  declined: "Recusada",
  cancelled: "Cancelada",
  expired: "Expirada",
};

/** Uma ação sobre uma oferta. O servidor é a fonte da verdade: depois dela (certa ou errada) a
 * lista é recarregada. Aceitar muda os donos dos itens, então também invalida o inventário. */
function useAcao(
  fn: (id: string) => Promise<unknown>,
  mexeNoInventario: boolean,
  avisar: (texto: string | null) => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onMutate: () => avisar(null),
    onError: (erro) => avisar(mensagemDoErro(erro)),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: TRADES_ROOT_KEY }),
        ...(mexeNoInventario
          ? [queryClient.invalidateQueries({ queryKey: INVENTORY_ROOT_KEY })]
          : []),
      ]),
  });
}

function Item({ item }: { item: TradeItem }) {
  const { skin } = item;
  return (
    <li className="flex flex-col gap-0.5 rounded-md border border-border p-3">
      <span className="font-semibold">{skin.name}</span>
      <span className="text-sm">{skin.weapon}</span>
      <span className="text-sm">{item.wear}</span>
      <span className="text-sm font-semibold">{formatUsd(item.reference_price)}</span>
    </li>
  );
}

function Lado({ titulo, itens }: { titulo: string; itens: TradeItem[] }) {
  return (
    <div role="group" aria-label={titulo} className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {titulo}
      </h3>
      <ul className="flex flex-col gap-2">
        {itens.map((item) => (
          <Item key={item.id} item={item} />
        ))}
      </ul>
    </div>
  );
}

interface CartaoProps {
  oferta: TradeOffer;
  meuUsername: string | undefined;
  ocupado: boolean;
  onAceitar: () => void;
  onRecusar: () => void;
  onCancelar: () => void;
}

function Cartao({ oferta, meuUsername, ocupado, onAceitar, onRecusar, onCancelar }: CartaoProps) {
  const { proposer, recipient } = oferta;
  const pendente = oferta.status === "pending";
  const souDestinatario = meuUsername === recipient.username;
  const souProponente = meuUsername === proposer.username;
  return (
    <article
      aria-label={`Oferta de ${proposer.username} para ${recipient.username}`}
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-6"
    >
      <header className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm">
          <Avatar avatar={proposer.avatar} username={proposer.username} />
          <span>{`${proposer.username} → ${recipient.username}`}</span>
        </span>
        <span className="text-sm text-muted-foreground">{ROTULO[oferta.status]}</span>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <Lado titulo="Oferecido" itens={oferta.items.filter((i) => i.side === "offered")} />
        <Lado titulo="Pedido" itens={oferta.items.filter((i) => i.side === "requested")} />
      </div>
      {pendente && souDestinatario && (
        <div className="flex gap-2">
          <ConfirmButton
            label="Aceitar"
            name={`oferta de ${proposer.username}`}
            disabled={ocupado}
            onConfirm={onAceitar}
          />
          <Button variant="outline" size="sm" disabled={ocupado} onClick={onRecusar}>
            Recusar
          </Button>
        </div>
      )}
      {pendente && souProponente && (
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={ocupado} onClick={onCancelar}>
            Cancelar oferta
          </Button>
        </div>
      )}
    </article>
  );
}

export default function TradesPage() {
  const { user } = useSession();
  const [pagina, setPagina] = useState(1);
  const ofertas = useTrades(pagina);
  const [aviso, setAviso] = useState<string | null>(null);

  const aceitar = useAcao(acceptTrade, true, setAviso);
  const recusar = useAcao(declineTrade, false, setAviso);
  const cancelar = useAcao(cancelTrade, false, setAviso);
  // Um clique por vez: enquanto qualquer ação corre, todos os botões de ação ficam travados.
  const ocupado = [aceitar, recusar, cancelar].some((a) => a.isPending);

  const dados = ofertas.data;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Trocas</h1>

      {ofertas.isError && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar suas ofertas. Tente novamente.
        </p>
      )}
      {aviso && (
        <p role="alert" className="text-sm text-primary">
          {aviso}
        </p>
      )}

      {dados?.results.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhuma oferta.</p>
      )}
      {dados && dados.results.length > 0 && (
        <>
          <div className="flex flex-col gap-4">
            {dados.results.map((oferta) => (
              <Cartao
                key={oferta.id}
                oferta={oferta}
                meuUsername={user?.username}
                ocupado={ocupado}
                onAceitar={() => aceitar.mutate(oferta.id)}
                onRecusar={() => recusar.mutate(oferta.id)}
                onCancelar={() => cancelar.mutate(oferta.id)}
              />
            ))}
          </div>
          <AtribuicaoSkinport />
        </>
      )}

      {dados && (dados.next || dados.previous) && (
        <nav aria-label="Páginas" className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!dados.previous}
            onClick={() => setPagina((p) => p - 1)}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!dados.next}
            onClick={() => setPagina((p) => p + 1)}
          >
            Próxima
          </Button>
        </nav>
      )}
    </main>
  );
}
