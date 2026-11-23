import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "../../components/ui/button";
import { ApiError } from "../../services/http";
import { sendRequest } from "../../services/friends";
import { Field } from "../auth/Field";
import { SENT_KEY } from "./useFriends";

// Mensagens por `code` do backend (apps/friends/services.py). Nunca o texto cru do servidor.
// `friendship_unavailable` é a mesma para inexistente, auto-pedido e bloqueado (anti-enumeração).
const MENSAGENS: Record<string, string> = {
  friendship_unavailable: "Não foi possível enviar o pedido a este jogador.",
  already_friends: "Vocês já são amigos.",
};
const GENERICA = "Não foi possível enviar o pedido. Tente novamente.";

export default function AddFriendForm() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const enviar = useMutation({
    mutationFn: sendRequest,
    onSuccess: () => setUsername(""),
    onSettled: () => queryClient.invalidateQueries({ queryKey: SENT_KEY }),
  });

  const nome = username.trim();
  const mensagem =
    enviar.error instanceof ApiError && enviar.error.code
      ? (MENSAGENS[enviar.error.code] ?? GENERICA)
      : GENERICA;

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    if (nome && !enviar.isPending) enviar.mutate(nome);
  }

  return (
    <form onSubmit={aoEnviar} className="flex flex-col gap-3">
      <Field
        id="novo-amigo"
        label="Nome de usuário"
        value={username}
        onChange={setUsername}
        autoComplete="off"
      />
      <div>
        <Button type="submit" disabled={!nome || enviar.isPending}>
          Enviar pedido
        </Button>
      </div>
      {enviar.isError && (
        <p role="alert" className="text-sm text-primary">
          {mensagem}
        </p>
      )}
    </form>
  );
}
