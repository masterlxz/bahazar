import { useQuery } from "@tanstack/react-query";

import { getInventory, type InventoryQuery } from "../../services/inventory";

// Chave hierárquica: um único `removeQueries(INVENTORY_ROOT_KEY)` no logout apaga o inventário
// de todos os jogadores que esta sessão chegou a ver.
export const INVENTORY_ROOT_KEY = ["inventory"] as const;

/** Meu inventário ("mine") ou o de um jogador ("user"): partes distintas, para que um jogador
 * chamado "mine" nunca colida com o meu. */
export const inventoryKey = (username: string | undefined, query: InventoryQuery) =>
  username === undefined
    ? ([...INVENTORY_ROOT_KEY, "mine", query] as const)
    : ([...INVENTORY_ROOT_KEY, "user", username, query] as const);

/**
 * Uma página do inventário (o meu ou o de um amigo) com os filtros dados, em cache.
 *
 * Sem `retry`: 404 (sem permissão ou página inexistente) e 400 (filtro inválido) são resultados
 * normais aqui e não mudam ao tentar de novo; com o padrão (3 tentativas com espera crescente) a
 * tela ficaria uns 7 s em "Carregando" antes de mostrar a mensagem.
 */
export function useInventory(username: string | undefined, query: InventoryQuery) {
  return useQuery({
    queryKey: inventoryKey(username, query),
    queryFn: () => getInventory(username, query),
    retry: false,
  });
}
