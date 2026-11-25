import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../services/http";
import { fetchSkins, fetchSkinDetail, fetchFacets, type CatalogQuery } from "../../services/skins";

export const SKINS_ROOT_KEY = ["skins"] as const;
export const FACETS_KEY = [...SKINS_ROOT_KEY, "facets"] as const;

export const skinsKey = (query: CatalogQuery) => [...SKINS_ROOT_KEY, "list", query] as const;
export const skinDetailKey = (id: string) => [...SKINS_ROOT_KEY, "detail", id] as const;

/** 4xx (filtro inválido, página inexistente) não muda ao tentar de novo. */
const tentarDeNovo = (tentativas: number, erro: Error) =>
  !(erro instanceof ApiError && erro.status >= 400 && erro.status < 500) && tentativas < 3;

/** Lista paginada de skins do catálogo com os filtros dados, em cache. */
export function useSkins(query: CatalogQuery) {
  return useQuery({
    queryKey: skinsKey(query),
    queryFn: () => fetchSkins(query),
    retry: tentarDeNovo,
  });
}

/** Detalhe de uma skin do catálogo. */
export function useSkinDetail(id: string) {
  return useQuery({
    queryKey: skinDetailKey(id),
    queryFn: () => fetchSkinDetail(id),
    retry: tentarDeNovo,
    enabled: id.length > 0,
  });
}

/** Facets do catálogo (raridades, armas, coleções, desgastes) — cache de 10 min. */
export function useFacets() {
  return useQuery({
    queryKey: FACETS_KEY,
    queryFn: fetchFacets,
    staleTime: 10 * 60 * 1000,
  });
}