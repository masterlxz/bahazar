import { useQuery } from "@tanstack/react-query";

import { getMe } from "../../services/me";

export const ME_KEY = ["me"] as const;

/** Perfil do jogador logado (`/api/v1/me/`), em cache. */
export function useMe() {
  return useQuery({ queryKey: ME_KEY, queryFn: getMe });
}
