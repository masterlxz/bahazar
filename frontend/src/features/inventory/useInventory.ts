import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../services/http";
import { getInventory, type InventoryQuery } from "../../services/inventory";
import { fetchFacets } from "../../services/skins";

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
 * "." e ".." não são nomes de jogador e, no caminho de uma URL, `encodeURIComponent` não os
 * codifica: `/api/v1/inventory/../` viraria `/api/v1/`. Nunca vão à API; a tela trata como 404.
 */
export const usernameImpossivel = (username: string | undefined) =>
  username === "." || username === "..";

/** 4xx (filtro inválido, sem permissão, página inexistente) não muda ao tentar de novo. */
const tentarDeNovo = (tentativas: number, erro: Error) =>
  !(erro instanceof ApiError && erro.status >= 400 && erro.status < 500) && tentativas < 3;

/**
 * Uma página do inventário (o meu ou o de um amigo) com os filtros dados, em cache.
 *
 * Sem retry em 4xx: 404 (sem permissão ou página inexistente) e 400 (filtro inválido) são
 * resultados normais aqui e não mudam ao tentar de novo; com o padrão (3 tentativas com espera
 * crescente) a tela ficaria uns 7 s em "Carregando" antes de mostrar a mensagem. Erro de rede e
 * 5xx seguem com até 3 tentativas, como no resto do app.
 */
export function useInventory(username: string | undefined, query: InventoryQuery) {
  return useQuery({
    queryKey: inventoryKey(username, query),
    queryFn: () => getInventory(username, query),
    enabled: !usernameImpossivel(username),
    retry: tentarDeNovo,
  });
}

/** Facets do catálogo (raridades, armas, coleções, desgastes) para popular os filtros do inventário. */
export function useInventoryFacets() {
  return useQuery({
    queryKey: ["inventory", "facets"],
    queryFn: fetchFacets,
    staleTime: 10 * 60 * 1000,
  });
}
