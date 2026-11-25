import type { CatalogSkin, CatalogSkinDetail, CatalogFacets, CatalogQuery, Paginated } from "../types/api";
import { request } from "./http";

const base = "/api/v1/catalog/";

/**
 * A query de uma consulta ao catálogo: só o que tem valor, SEMPRE na mesma ordem.
 * Assim a mesma consulta dá a mesma URL (a tela usa estes parâmetros também na barra de endereço).
 */
export function catalogParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const campo of ["rarity", "weapon", "collection", "wear", "q", "ordering"] as const) {
    const valor = query[campo];
    if (valor) params.set(campo, valor);
  }
  if (query.page) params.set("page", String(query.page));
  return params;
}

/** Lista paginada de skins do catálogo com os filtros dados. */
export function fetchSkins(query: CatalogQuery = {}): Promise<Paginated<CatalogSkin>> {
  const texto = catalogParams(query).toString();
  return request<Paginated<CatalogSkin>>(texto ? `${base}?${texto}` : base);
}

/** Detalhe de uma skin do catálogo. */
export function fetchSkinDetail(id: string): Promise<CatalogSkinDetail> {
  return request<CatalogSkinDetail>(`${base}${encodeURIComponent(id)}/`);
}

/** Facets do catálogo (raridades, armas, coleções, desgastes) para popular os filtros. */
export function fetchFacets(): Promise<CatalogFacets> {
  return request<CatalogFacets>(`${base}facets/`);
}