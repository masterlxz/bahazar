import type { CatalogSkin, CatalogSkinDetail, CatalogFacets, CatalogQuery, Paginated } from "../types/api";
import { request } from "./http";

export type { CatalogQuery, CatalogFacets };

const base = "/api/v1/catalog/";

/** Parâmetros da consulta ao catálogo: só o que tem valor, SEMPRE na mesma ordem. */
export function catalogParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const campo of ["rarity", "weapon", "collection", "wear", "q", "ordering"] as const) {
    const valor = query[campo];
    if (valor) params.set(campo, valor);
  }
  if (query.page) params.set("page", String(query.page));
  return params;
}

/** Lista paginada de skins do catálogo com filtros. */
export function fetchSkins(query: CatalogQuery = {}): Promise<Paginated<CatalogSkin>> {
  const texto = catalogParams(query).toString();
  return request<Paginated<CatalogSkin>>(texto ? `${base}?${texto}` : base);
}

/** Detalhe de uma skin do catálogo. */
export function fetchSkinDetail(id: string): Promise<CatalogSkinDetail> {
  return request<CatalogSkinDetail>(`${base}${encodeURIComponent(id)}/`);
}

/** Facets do catálogo (valores possíveis para filtros). */
export function fetchFacets(): Promise<CatalogFacets> {
  return request<CatalogFacets>(`${base}facets/`);
}