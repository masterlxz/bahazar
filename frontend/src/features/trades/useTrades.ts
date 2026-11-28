import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getTrades } from "../../services/trades";

// Chave hierárquica: um único `removeQueries(TRADES_ROOT_KEY)` no logout apaga as listas todas.
export const TRADES_ROOT_KEY = ["trades"] as const;

/** Uma página das ofertas de que o jogador faz parte. Mantém a página anterior na tela enquanto
 * a próxima carrega, para a lista não piscar. */
export function useTrades(pagina: number) {
  return useQuery({
    queryKey: [...TRADES_ROOT_KEY, "list", pagina] as const,
    queryFn: () => getTrades(pagina),
    placeholderData: keepPreviousData,
  });
}
