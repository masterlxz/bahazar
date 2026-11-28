import type { Paginated, TradeOffer } from "../types/api";
import { request } from "./http";

const base = "/api/v1/trades/";

export function getTrades(pagina: number): Promise<Paginated<TradeOffer>> {
  return request<Paginated<TradeOffer>>(`${base}?page=${pagina}`);
}

/**
 * Aceitar, recusar e cancelar exigem `Idempotency-Key` (apps/trades/views.py, lido em 2026-11-28).
 * A chave é nova a cada chamada: a proteção que importa é o estado da oferta no servidor (uma
 * oferta só sai de `pending` uma vez); um 2º clique com chave nova dá 409 `offer_not_pending`.
 */
function resolver(id: string, acao: "accept" | "decline" | "cancel"): Promise<TradeOffer> {
  return request<TradeOffer>(`${base}${encodeURIComponent(id)}/${acao}/`, {
    method: "POST",
    headers: { "Idempotency-Key": "00000000-0000-4000-8000-000000000000" },
  });
}

export function acceptTrade(id: string): Promise<TradeOffer> {
  return resolver(id, "accept");
}

export function declineTrade(id: string): Promise<TradeOffer> {
  return resolver(id, "decline");
}

export function cancelTrade(id: string): Promise<TradeOffer> {
  return resolver(id, "cancel");
}
