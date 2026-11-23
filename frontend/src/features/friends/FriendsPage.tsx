import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { Avatar } from "../../components/ui/avatar";
import { Button } from "../../components/ui/button";
import { ConfirmButton } from "../../components/ui/ConfirmButton";
import {
  acceptRequest,
  blockUser,
  declineRequest,
  removeFriend,
  unblockUser,
} from "../../services/friends";
import { ApiError } from "../../services/http";
import AddFriendForm from "./AddFriendForm";
import {
  BLOCKED_KEY,
  FRIENDS_LIST_KEY,
  REQUESTS_KEY,
  SENT_KEY,
  useFriendLists,
} from "./useFriends";

const MUDOU = "Isso mudou. Atualizamos a lista.";
const FALHOU = "Não foi possível concluir a ação. Tente novamente.";

/** Uma ação sobre as listas. O servidor é a fonte da verdade: depois dela, as listas afetadas
 * são recarregadas (e o botão segue ocupado até lá), em vez de editadas "de cabeça". */
function useAcao<V>(
  fn: (valor: V) => Promise<unknown>,
  invalidar: readonly (readonly string[])[],
  avisar: (texto: string | null) => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onMutate: () => avisar(null),
    onError: (erro) => avisar(erro instanceof ApiError && erro.status === 404 ? MUDOU : FALHOU),
    onSettled: () =>
      Promise.all(invalidar.map((chave) => queryClient.invalidateQueries({ queryKey: chave }))),
  });
}

function Secao({ id, titulo, children }: { id: string; titulo: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6"
    >
      <h2
        id={id}
        className="text-sm font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Linha({ username, children }: { username: string; children?: ReactNode }) {
  return (
    <li className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-3">
        <Avatar avatar="default" username={username} />
        {username}
      </span>
      <span className="flex gap-2">{children}</span>
    </li>
  );
}

export default function FriendsPage() {
  const { amigos, recebidos, enviados, bloqueados } = useFriendLists();
  const [aviso, setAviso] = useState<string | null>(null);

  const aceitar = useAcao(acceptRequest, [FRIENDS_LIST_KEY, REQUESTS_KEY], setAviso);
  const recusar = useAcao(declineRequest, [REQUESTS_KEY], setAviso);
  const remover = useAcao(removeFriend, [FRIENDS_LIST_KEY], setAviso);
  const bloquear = useAcao(
    blockUser,
    [REQUESTS_KEY, SENT_KEY, BLOCKED_KEY],
    setAviso,
  );
  const desbloquear = useAcao(unblockUser, [BLOCKED_KEY], setAviso);

  // Um clique por vez: enquanto qualquer ação corre, todos os botões de ação ficam travados.
  const ocupado = [aceitar, recusar, remover, bloquear, desbloquear].some((a) => a.isPending);
  const falhouAoCarregar = [amigos, recebidos, enviados, bloqueados].some((q) => q.isError);

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Amigos</h1>

      {falhouAoCarregar && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar suas listas de amigos. Tente novamente.
        </p>
      )}
      {aviso && (
        <p role="alert" className="text-sm text-primary">
          {aviso}
        </p>
      )}

      <Secao id="sec-adicionar" titulo="Adicionar amigo">
        <AddFriendForm />
      </Secao>

      <Secao id="sec-recebidos" titulo="Pedidos recebidos">
        {recebidos.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum pedido recebido.</p>
        )}
        <ul className="flex flex-col gap-3">
          {recebidos.data?.map((pedido) => (
            <Linha key={pedido.id} username={pedido.requester}>
              <Button
                size="sm"
                disabled={ocupado}
                aria-label={`Aceitar ${pedido.requester}`}
                onClick={() => aceitar.mutate(pedido.id)}
              >
                Aceitar
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={ocupado}
                aria-label={`Recusar ${pedido.requester}`}
                onClick={() => recusar.mutate(pedido.id)}
              >
                Recusar
              </Button>
            </Linha>
          ))}
        </ul>
      </Secao>

      <Secao id="sec-enviados" titulo="Pedidos enviados">
        {enviados.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum pedido enviado.</p>
        )}
        <ul className="flex flex-col gap-3">
          {enviados.data?.map((pedido) => <Linha key={pedido.id} username={pedido.addressee} />)}
        </ul>
      </Secao>

      <Secao id="sec-amigos" titulo="Seus amigos">
        {amigos.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Você ainda não tem amigos.</p>
        )}
        <ul className="flex flex-col gap-3">
          {amigos.data?.map((amigo) => (
            <li key={amigo.username} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-3">
                <Avatar avatar={amigo.avatar} username={amigo.username} />
                {amigo.username}
              </span>
              <span className="flex gap-2">
                <ConfirmButton
                  label="Remover"
                  name={amigo.username}
                  disabled={ocupado}
                  onConfirm={() => remover.mutate(amigo.username)}
                />
                <ConfirmButton
                  label="Bloquear"
                  name={amigo.username}
                  disabled={ocupado}
                  onConfirm={() => bloquear.mutate(amigo.username)}
                />
              </span>
            </li>
          ))}
        </ul>
      </Secao>

      <Secao id="sec-bloqueados" titulo="Bloqueados">
        {bloqueados.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Você não bloqueou ninguém.</p>
        )}
        <ul className="flex flex-col gap-3">
          {bloqueados.data?.map((pessoa) => (
            <li key={pessoa.username} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-3">
                <Avatar avatar={pessoa.avatar} username={pessoa.username} />
                {pessoa.username}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={ocupado}
                aria-label={`Desbloquear ${pessoa.username}`}
                onClick={() => desbloquear.mutate(pessoa.username)}
              >
                Desbloquear
              </Button>
            </li>
          ))}
        </ul>
      </Secao>
    </main>
  );
}
