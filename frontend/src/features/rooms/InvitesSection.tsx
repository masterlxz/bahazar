import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "../../components/ui/button";
import { ConfirmButton } from "../../components/ui/ConfirmButton";
import { formatDateTime } from "../../lib/datetime";
import { ApiError } from "../../services/http";
import { createInvite, revokeInvite } from "../../services/rooms";
import type { RoomInvite } from "../../types/api";
import { Field } from "../auth/Field";
import { invitesKey, useInvites } from "./useRooms";

// Estado em português; quem decide o estado é o servidor (`status`), não esta tela.
const ESTADO: Record<RoomInvite["status"], string> = {
  ok: "Ativo",
  expired: "Expirado",
  exhausted: "Esgotado",
  revoked: "Revogado",
};

// Mensagens por `code`/status do backend (apps/rooms/services.py). Nunca o texto cru do servidor.
// Os tetos citados (30 dias, 50 usos, 10 ativos) são do backend (rules.py); aqui só a mensagem.
const LIMITE = "A sala já tem 10 convites ativos. Revogue um para gerar outro.";
const POLITICA = "Use de 1 a 30 dias e de 1 a 50 usos.";
const SEM_PERMISSAO = "Só o dono ou um administrador pode gerar convites.";
const FALHOU_AO_GERAR = "Não foi possível gerar o convite. Tente novamente.";
const MUDOU = "Isso mudou. Atualizamos a lista.";
const FALHOU_AO_REVOGAR = "Não foi possível revogar o convite. Tente novamente.";
const NAO_COPIOU = "Não foi possível copiar. Selecione o código e copie à mão.";

function mensagemAoGerar(erro: unknown): string {
  if (erro instanceof ApiError) {
    if (erro.code === "invite_limit_reached") return LIMITE;
    if (erro.status === 400) return POLITICA;
    if (erro.status === 403) return SEM_PERMISSAO;
  }
  return FALHOU_AO_GERAR;
}

const inteiroPositivo = (texto: string) => {
  const n = Number(texto);
  return texto.trim() !== "" && Number.isInteger(n) && n >= 1 ? n : null;
};

export default function InvitesSection({ roomId }: { roomId: string }) {
  const queryClient = useQueryClient();
  const convites = useInvites(roomId);
  const [dias, setDias] = useState("7");
  const [usos, setUsos] = useState("10");
  // O código é um SEGREDO mostrado uma vez: vive só neste estado, nunca no cache do React Query,
  // em armazenamento, URL ou log. "Fechar" e sair da página o apagam.
  const [codigo, setCodigo] = useState<string | null>(null);
  const [copia, setCopia] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const recarregar = () => queryClient.invalidateQueries({ queryKey: invitesKey(roomId) });

  const gerar = useMutation({
    gcTime: 0, // o código também não fica no cache de mutações depois que a tela sai
    mutationFn: (v: { dias: number; usos: number }) => createInvite(roomId, v.dias, v.usos),
    onSuccess: (convite) => {
      setCodigo(convite.code);
      setCopia(null);
    },
    onSettled: recarregar,
  });

  const revogar = useMutation({
    mutationFn: (id: string) => revokeInvite(roomId, id),
    onMutate: () => setAviso(null),
    onError: (e) => setAviso(e instanceof ApiError && e.status === 404 ? MUDOU : FALHOU_AO_REVOGAR),
    onSettled: recarregar,
  });

  const nDias = inteiroPositivo(dias);
  const nUsos = inteiroPositivo(usos);
  const ocupado = gerar.isPending || revogar.isPending;

  function aoGerar(evento: FormEvent) {
    evento.preventDefault();
    if (nDias !== null && nUsos !== null && !ocupado) gerar.mutate({ dias: nDias, usos: nUsos });
  }

  async function copiar(texto: string) {
    try {
      await navigator.clipboard.writeText(texto);
      setCopia("Código copiado.");
    } catch {
      // Sem `navigator.clipboard` (contexto não seguro) ou permissão negada.
      setCopia(NAO_COPIOU);
    }
  }

  function fechar() {
    setCopia(null);
    gerar.reset();
  }

  return (
    <section
      aria-labelledby="sec-convites"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-6"
    >
      <h2
        id="sec-convites"
        className="text-sm font-semibold uppercase tracking-wide text-muted-foreground"
      >
        Convites
      </h2>

      <form onSubmit={aoGerar} className="flex flex-col gap-3">
        <Field
          id="convite-dias"
          label="Validade (dias)"
          type="number"
          value={dias}
          onChange={setDias}
          hint="De 1 a 30 dias"
        />
        <Field
          id="convite-usos"
          label="Usos máximos"
          type="number"
          value={usos}
          onChange={setUsos}
          hint="De 1 a 50 usos"
        />
        <div>
          <Button type="submit" disabled={nDias === null || nUsos === null || ocupado}>
            Gerar convite
          </Button>
        </div>
        {gerar.isError && (
          <p role="alert" className="text-sm text-primary">
            {mensagemAoGerar(gerar.error)}
          </p>
        )}
      </form>

      {codigo && (
        <section
          aria-labelledby="sec-novo-convite"
          className="flex flex-col gap-3 rounded-md border border-primary p-4"
        >
          <h3 id="sec-novo-convite" className="text-sm font-semibold">
            Novo convite
          </h3>
          <code className="break-all rounded bg-secondary px-3 py-2 text-sm">{codigo}</code>
          <p className="text-sm text-muted-foreground">
            Guarde este código agora. Ele não será mostrado de novo.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => void copiar(codigo)}>
              Copiar código
            </Button>
            <Button variant="ghost" size="sm" onClick={fechar}>
              Fechar
            </Button>
          </div>
          {copia && (
            <p role="status" className="text-sm">
              {copia}
            </p>
          )}
        </section>
      )}

      {convites.isError && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar os convites. Tente novamente.
        </p>
      )}
      {aviso && (
        <p role="alert" className="text-sm text-primary">
          {aviso}
        </p>
      )}

      {convites.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhum convite ainda.</p>
      )}
      <ul className="flex flex-col gap-3">
        {convites.data?.map((convite, i) => (
          <li key={convite.id} className="flex items-center justify-between gap-3">
            <span className="flex flex-col">
              <span className="font-medium">{ESTADO[convite.status]}</span>
              <span className="text-sm text-muted-foreground">
                {`${convite.uses} de ${convite.max_uses} usos`}
              </span>
              <span className="text-sm text-muted-foreground">
                {`Expira em ${formatDateTime(convite.expires_at)}`}
              </span>
            </span>
            {convite.status === "ok" && (
              <ConfirmButton
                label="Revogar"
                name={`convite ${i + 1}`}
                disabled={ocupado}
                onConfirm={() => revogar.mutate(convite.id)}
              />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
