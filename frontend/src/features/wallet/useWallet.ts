import { useQuery } from "@tanstack/react-query";

import { getWallet } from "../../services/wallet";

export const WALLET_KEY = ["wallet"] as const;

/** Carteira do jogador logado (`/api/v1/wallet/`), em cache. */
export function useWallet() {
  return useQuery({ queryKey: WALLET_KEY, queryFn: getWallet });
}
