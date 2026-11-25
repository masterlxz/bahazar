import type { InventoryItem, Paginated } from "../types/api";
import { request } from "./http";

const base = "/api/v1/inventory/";

/** Os filtros e a página de uma consulta ao inventário (nomes iguais aos da API). */
export interface InventoryQuery {
  rarity?: string;
  weapon?: string;
  collection?: string;
  wear?: string;
  q?: string;
  ordering?: string;
  /** A partir de 1; ausente vale 1. */
  page?: number;
}

/**
 * A query de uma consulta: só o que tem valor, SEMPRE na mesma ordem. Assim a mesma consulta dá
 * a mesma URL (a tela usa estes parâmetros também na barra de endereço).
 */
export function inventoryParams(query: InventoryQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const campo of ["rarity", "weapon", "collection", "wear", "q", "ordering"] as const) {
    const valor = query[campo];
    if (valor) params.set(campo, valor);
  }
  if (query.page) params.set("page", String(query.page));
  return params;
}

/**
 * O inventário do jogador logado (`username` ausente) ou o de um amigo. Quem não pode ver recebe
 * 404 do servidor, igual para todos os motivos: o chamador não deve distingui-los.
 */
export function getInventory(
  username: string | undefined,
  query: InventoryQuery = {},
): Promise<Paginated<InventoryItem>> {
  const caminho = username === undefined ? base : `${base}${encodeURIComponent(username)}/`;
  const texto = inventoryParams(query).toString();
  return request<Paginated<InventoryItem>>(texto ? `${caminho}?${texto}` : caminho);
}
