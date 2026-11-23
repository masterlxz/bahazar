import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button } from "../../components/ui/button";
import { ApiError } from "../../services/http";
import { joinRoom } from "../../services/rooms";
import { Field } from "../auth/Field";
import { ROOMS_LIST_KEY } from "./useRooms";

// Mensagens por `code` do backend (apps/rooms/services.py). Nunca o texto cru do servidor, e
// nunca o código digitado: o segredo não é repetido na tela.
const POR_CODIGO: Record<string, string> = {
  invite_expired: "Este convite expirou.",
  invite_revoked: "Este convite foi revogado.",
  invite_exhausted: "Este convite já foi usado o máximo de vezes.",
  room_full: "A sala está cheia.",
  room_archived: "A sala foi arquivada.",
};
const NAO_ENCONTRADO = "Convite não encontrado."; // código errado OU banido: o servidor não distingue
const MUITAS_TENTATIVAS = "Muitas tentativas. Espere um minuto e tente de novo.";
const SEM_CODIGO = "Informe o código do convite.";
const GENERICA = "Não foi possível entrar no grupo. Tente novamente.";

function mensagemDe(erro: unknown): string {
  if (erro instanceof ApiError) {
    if (erro.status === 429) return MUITAS_TENTATIVAS;
    if (erro.status === 404) return NAO_ENCONTRADO;
    const doCodigo = erro.code ? POR_CODIGO[erro.code] : undefined;
    if (doCodigo) return doCodigo;
    if (erro.status === 400) return SEM_CODIGO;
  }
  return GENERICA;
}

export default function JoinRoomForm() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [codigoDigitado, setCodigoDigitado] = useState("");
  const entrar = useMutation({
    mutationFn: joinRoom,
    onSuccess: async (sala) => {
      await queryClient.invalidateQueries({ queryKey: ROOMS_LIST_KEY });
      setCodigoDigitado("");
      navigate(`/grupos/${sala.id}`);
    },
  });

  const codigo = codigoDigitado.trim();

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    if (codigo && !entrar.isPending) entrar.mutate(codigo);
  }

  return (
    <form onSubmit={aoEnviar} className="flex flex-col gap-3">
      <Field
        id="codigo-convite"
        label="Código do convite"
        value={codigoDigitado}
        onChange={setCodigoDigitado}
        autoComplete="off"
      />
      <div>
        <Button type="submit" disabled={!codigo || entrar.isPending}>
          Entrar no grupo
        </Button>
      </div>
      {entrar.isError && (
        <p role="alert" className="text-sm text-primary">
          {mensagemDe(entrar.error)}
        </p>
      )}
    </form>
  );
}
