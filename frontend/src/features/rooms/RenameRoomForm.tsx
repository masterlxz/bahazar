import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "../../components/ui/button";
import { ApiError } from "../../services/http";
import { renameRoom } from "../../services/rooms";
import type { Room } from "../../types/api";
import { Field } from "../auth/Field";
import { ROOMS_LIST_KEY, roomKey } from "./useRooms";

const NOME_INVALIDO = "Informe um nome de 1 a 60 caracteres.";
const GENERICA = "Não foi possível renomear. Tente novamente.";

export default function RenameRoomForm({ sala }: { sala: Room }) {
  const queryClient = useQueryClient();
  const [nomeDigitado, setNomeDigitado] = useState(sala.name);
  const renomear = useMutation({
    mutationFn: (nome: string) => renameRoom(sala.id, nome),
    // Só no sucesso: o servidor é a fonte da verdade, então recarrega o detalhe e a lista.
    onSuccess: async (_, nome) => {
      setNomeDigitado(nome);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: roomKey(sala.id) }),
        queryClient.invalidateQueries({ queryKey: ROOMS_LIST_KEY }),
      ]);
    },
  });

  const nome = nomeDigitado.trim();

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    if (nome && nome !== sala.name && !renomear.isPending) renomear.mutate(nome);
  }

  const mensagem =
    renomear.error instanceof ApiError && renomear.error.status === 400
      ? NOME_INVALIDO
      : GENERICA;

  return (
    <form onSubmit={aoEnviar} className="flex flex-col gap-3">
      <Field
        id="renomear-grupo"
        label="Nome do grupo"
        value={nomeDigitado}
        onChange={setNomeDigitado}
        autoComplete="off"
      />
      <div>
        <Button type="submit" disabled={!nome || nome === sala.name || renomear.isPending}>
          Renomear
        </Button>
      </div>
      {renomear.isError && (
        <p role="alert" className="text-sm text-primary">
          {mensagem}
        </p>
      )}
    </form>
  );
}
