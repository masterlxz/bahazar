import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { Avatar } from "../../components/ui/avatar";
import { ConfirmButton } from "../../components/ui/ConfirmButton";
import { ApiError } from "../../services/http";
import { leaveRoom } from "../../services/rooms";
import type { Room } from "../../types/api";
import RenameRoomForm from "./RenameRoomForm";
import { PAPEL, ROOMS_LIST_KEY, membersKey, podeGerenciar, roomKey, useMembers, useRoom } from "./useRooms";

const FALHOU_AO_SAIR = "Não foi possível sair do grupo. Tente novamente.";

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

function SairDoGrupo({ sala }: { sala: Room }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [erro, setErro] = useState<string | null>(null);

  // Saiu (ou já tinha saído em outra aba, 404): volta à lista e esquece o que sabia da sala.
  function terminou() {
    void queryClient.invalidateQueries({ queryKey: ROOMS_LIST_KEY });
    navigate("/grupos");
    queryClient.removeQueries({ queryKey: roomKey(sala.id) });
    queryClient.removeQueries({ queryKey: membersKey(sala.id) });
  }

  const sair = useMutation({
    mutationFn: () => leaveRoom(sala.id),
    onMutate: () => setErro(null),
    onSuccess: terminou,
    onError: (e) => {
      if (e instanceof ApiError && e.status === 404) terminou();
      else setErro(FALHOU_AO_SAIR);
    },
  });

  // O dono nunca sai (uma sala não fica sem dono); o backend também recusa com 409.
  if (sala.max_members < 0) {
    return <p className="text-sm text-muted-foreground">O dono não pode sair do grupo.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      <div>
        <ConfirmButton
          label="Sair"
          name={sala.name}
          disabled={sair.isPending}
          onConfirm={() => sair.mutate()}
        />
      </div>
      {erro && (
        <p role="alert" className="text-sm text-primary">
          {erro}
        </p>
      )}
    </div>
  );
}

export default function RoomDetailPage() {
  const { roomId = "" } = useParams();
  const sala = useRoom(roomId);
  const membros = useMembers(roomId);

  if (sala.isError) {
    const naoExiste = sala.error instanceof ApiError && sala.error.status === 404;
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-12">
        <p role={naoExiste ? undefined : "alert"} className="text-sm text-primary">
          {naoExiste ? "Grupo não encontrado." : "Não foi possível carregar o grupo. Tente novamente."}
        </p>
        <Link to="/grupos" className="text-sm hover:underline">
          Voltar aos grupos
        </Link>
      </main>
    );
  }
  if (!sala.data) return null;

  const grupo = sala.data;
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">{grupo.name}</h1>
        <p className="text-sm text-muted-foreground">{`Seu papel: ${PAPEL[grupo.role]}`}</p>
      </header>

      <Secao id="sec-membros" titulo="Membros">
        {membros.isError && (
          <p role="alert" className="text-sm text-primary">
            Não foi possível carregar os membros. Tente novamente.
          </p>
        )}
        {membros.data && (
          <>
            <p className="text-sm text-muted-foreground">
              {`${membros.data.length} de ${grupo.max_members} membros`}
            </p>
            <ul className="flex flex-col gap-3">
              {membros.data.map((m) => (
                <li key={m.username} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-3">
                    <Avatar avatar={m.avatar} username={m.username} />
                    {m.username}
                  </span>
                  <span className="text-sm text-muted-foreground">{PAPEL[m.role]}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Secao>

      {podeGerenciar(grupo.role) && (
        <Secao id="sec-renomear" titulo="Renomear grupo">
          <RenameRoomForm key={grupo.id} sala={grupo} />
        </Secao>
      )}

      <SairDoGrupo sala={grupo} />
    </main>
  );
}
