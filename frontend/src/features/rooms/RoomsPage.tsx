import type { ReactNode } from "react";
import { Link } from "react-router";

import CreateRoomForm from "./CreateRoomForm";
import JoinRoomForm from "./JoinRoomForm";
import { PAPEL, useRooms } from "./useRooms";

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

export default function RoomsPage() {
  const salas = useRooms();

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Grupos</h1>

      {salas.isError && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar seus grupos. Tente novamente.
        </p>
      )}

      <Secao id="sec-grupos" titulo="Seus grupos">
        {salas.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Você ainda não está em nenhum grupo.</p>
        )}
        <ul className="flex flex-col gap-3">
          {salas.data?.map((sala) => (
            <li key={sala.id} className="flex items-center justify-between gap-3">
              <Link to={`/grupos/${sala.id}`} className="font-medium hover:underline">
                {sala.name}
              </Link>
              <span className="text-sm text-muted-foreground">{PAPEL[sala.role]}</span>
            </li>
          ))}
        </ul>
      </Secao>

      <Secao id="sec-criar" titulo="Criar grupo">
        <CreateRoomForm />
      </Secao>

      <Secao id="sec-entrar" titulo="Entrar com código">
        <JoinRoomForm />
      </Secao>
    </main>
  );
}
