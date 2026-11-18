import type { ReactNode } from "react";
import { Navigate } from "react-router";

import { useSession } from "./useSession";

/** Só renderiza `children` com sessão; sem sessão, manda para /entrar. */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useSession();

  if (status === "loading") {
    return <p className="px-4 py-12 text-center text-muted-foreground">Carregando…</p>;
  }
  if (status === "anonymous") {
    return <Navigate to="/entrar" replace />;
  }
  return children;
}
