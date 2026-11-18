import { useQuery } from "@tanstack/react-query";

import { getSession } from "../../services/auth";
import type { SessionUser } from "../../types/api";

export const SESSION_KEY = ["session"] as const;

export type SessionState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: SessionUser };

/** Estado da sessão como dado de servidor (cache do TanStack Query), não estado local. */
export function useSession(): SessionState {
  const { data, isPending } = useQuery({
    queryKey: SESSION_KEY,
    queryFn: getSession,
    staleTime: 60_000,
  });

  if (isPending) return { status: "loading", user: null };
  if (data) return { status: "authenticated", user: data };
  return { status: "anonymous", user: null };
}
