import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { SESSION_KEY, useSession } from "../../features/auth/useSession";
import { ME_KEY } from "../../features/profile/useMe";
import { WALLET_KEY } from "../../features/wallet/useWallet";
import { logout } from "../../services/auth";
import { Button } from "../ui/button";

export default function Header() {
  const { status } = useSession();
  const queryClient = useQueryClient();

  async function sair() {
    await logout();
    // Sem navigate() aqui, de propósito: a sessão é a única fonte de verdade. Ao ficar anônima,
    // o RequireAuth leva ao login se a página for protegida; numa página pública não muda nada.
    // (Um navigate("/") explícito disputaria com esse redirecionamento e o último venceria.)
    await queryClient.invalidateQueries({ queryKey: SESSION_KEY });
    // O perfil do usuário que saiu não pode sobrar em cache para o próximo que entrar.
    queryClient.removeQueries({ queryKey: ME_KEY });
    // Idem para o saldo: dado de dinheiro de um usuário nunca pode aparecer para o próximo.
    void WALLET_KEY;
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
              <Link to="/carteira" className="hover:underline">
                Carteira
              </Link>
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
