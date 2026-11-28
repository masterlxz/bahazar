import type { Paginated, TradeOffer } from "../types/api";

// ESQUELETO (Etapa D): compila e não faz nada, para os testes falharem por asserção.
// (Sem parâmetros de propósito: o lint recusa parâmetro sem uso, e nada aqui chama estas funções.)

export function getTrades(): Promise<Paginated<TradeOffer>> {
  return Promise.reject(new Error("não implementado"));
}

export function acceptTrade(): Promise<TradeOffer> {
  return Promise.reject(new Error("não implementado"));
}

export function declineTrade(): Promise<TradeOffer> {
  return Promise.reject(new Error("não implementado"));
}

export function cancelTrade(): Promise<TradeOffer> {
  return Promise.reject(new Error("não implementado"));
}
