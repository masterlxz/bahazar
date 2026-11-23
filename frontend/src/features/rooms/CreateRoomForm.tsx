import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button } from "../../components/ui/button";
import { ApiError } from "../../services/http";
import { createRoom } from "../../services/rooms";
import { Field } from "../auth/Field";
import { ROOMS_LIST_KEY } from "./useRooms";

// O teto de 5 salas como dono é do backend (rules.MAX_ROOMS_AS_OWNER); aqui só a mensagem.
const LIMITE = "Você já é dono de 5 grupos.";
const NOME_INVALIDO = "Informe um nome de 1 a 60 caracteres.";
const GENERICA = "Não foi possível criar o grupo. Tente novamente.";

function mensagemDe(erro: unknown): string {
  if (erro instanceof ApiError) {
    if (erro.code === "room_limit_reached") return LIMITE;
    if (erro.status === 400) return NOME_INVALIDO;
  }
  return GENERICA;
}

export default function CreateRoomForm() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [nomeDigitado, setNomeDigitado] = useState("");
  const criar = useMutation({
    mutationFn: createRoom,
    onSuccess: async (sala) => {
      await queryClient.invalidateQueries({ queryKey: ROOMS_LIST_KEY });
      setNomeDigitado("");
      navigate(`/grupos/${sala.id}`);
    },
  });

  const nome = nomeDigitado.trim();

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    if (nome && !criar.isPending) criar.mutate(nome);
  }

  return (
    <form onSubmit={aoEnviar} className="flex flex-col gap-3">
      <Field
        id="novo-grupo"
        label="Nome do grupo"
        value={nomeDigitado}
        onChange={setNomeDigitado}
        autoComplete="off"
      />
      <div>
        <Button type="submit" disabled={!nome || criar.isPending}>
          Criar grupo
        </Button>
      </div>
      {criar.isError && (
        <p role="alert" className="text-sm text-primary">
          {mensagemDe(criar.error)}
        </p>
      )}
    </form>
  );
}
