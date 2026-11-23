import { useQuery } from "@tanstack/react-query";

import { getBlocked, getFriends, getReceivedRequests, getSentRequests } from "../../services/friends";

// Chaves hierárquicas: um único `removeQueries(FRIENDS_ROOT_KEY)` no logout apaga todas.
export const FRIENDS_ROOT_KEY = ["friends"] as const;
export const FRIENDS_LIST_KEY = ["friends", "list"] as const;
export const REQUESTS_KEY = ["friends", "requests"] as const;
export const SENT_KEY = ["friends", "sent"] as const;
export const BLOCKED_KEY = ["friends", "blocked"] as const;

/** As quatro listas da tela de amigos, cada uma em cache. */
export function useFriendLists() {
  const amigos = useQuery({ queryKey: FRIENDS_LIST_KEY, queryFn: getFriends });
  const recebidos = useQuery({ queryKey: REQUESTS_KEY, queryFn: getReceivedRequests });
  const enviados = useQuery({ queryKey: SENT_KEY, queryFn: getSentRequests });
  const bloqueados = useQuery({ queryKey: BLOCKED_KEY, queryFn: getBlocked });
  return { amigos, recebidos, enviados, bloqueados };
}
