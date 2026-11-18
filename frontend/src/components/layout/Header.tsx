import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";

import { SESSION_KEY, useSession } from "../../features/auth/useSession";
import { ME_KEY } from "../../features/profile/useMe";
import { logout } from "../../services/auth";
import { Button } from "../ui/button";

export default function Header() {
  const { status } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  async function sair() {
    await logout();
    // Navega ANTES de invalidar: com a sessão já invalidada, o RequireAuth redirecionaria
    // para /entrar e o jogador não voltaria ao início.
    navigate("/");
    queryClient.removeQueries({ queryKey: ME_KEY });
    await queryClient.invalidateQueries({ queryKey: SESSION_KEY });
  }

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
        <Link to="/" className="text-lg font-bold tracking-tight">
          bahazar
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {status === "authenticated" && (
            <>
              <Link to="/perfil" className="hover:underline">
                Perfil
              </Link>
              <Button variant="ghost" size="sm" onClick={sair}>
                Sair
              </Button>
            </>
          )}
          {status === "anonymous" && (
            <>
              <Link to="/entrar" className="hover:underline">
                Entrar
              </Link>
              <Link to="/cadastrar" className="hover:underline">
                Cadastrar
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
