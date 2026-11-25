import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";

import { Button } from "../../components/ui/button";

import { ApiError } from "../../services/http";
import { catalogParams, type CatalogQuery } from "../../services/skins";
import type { CatalogSkin } from "../../types/api";
import type { CatalogFacets } from "../../types/api";
import { DEFAULT_ORDERING, ORDENACOES, lerConsulta, normalizar, opcoesRarity, opcoesWeapon, opcoesCollection, opcoesWear } from "./consulta";
import { SkinCard } from "./components/SkinCard";
import { Filtros } from "./components/SkinsFilters";
import { SkinsPagination } from "./components/SkinsPagination";
import { useSkins, useFacets } from "./useSkins";

const CLASSE_CAMPO =
  "h-10 rounded-md border border-border bg-secondary px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function Campo({ id, rotulo, children }: { id: string; rotulo: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {rotulo}
      </label>
      {children}
    </div>
  );
}

export default function SkinsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const consulta = lerConsulta(searchParams);
  const pagina = consulta.page ?? 1;
  const skins = useSkins(consulta);
  const facets = useFacets();

  // A consulta mora na URL: voltar do navegador desfaz um filtro, e o link é compartilhável.
  const ir = (nova: CatalogQuery) => setSearchParams(catalogParams(normalizar(nova)));
  const status = skins.error instanceof ApiError ? skins.error.status : null;
  // Só um sucesso mostra itens. Um refetch que falha MANTÉM `data` no TanStack Query; usar
  // `skins.data` aqui exibiria o catálogo antigo junto com a mensagem de erro.
  const dados = skins.isSuccess ? skins.data : null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Catálogo de Skins</h1>

      <Filtros
        key={`${searchParams.toString()}`}
        consulta={consulta}
        facets={facets.data}
        onAplicar={ir}
        onLimpar={() => ir({})}
      />

      {skins.isPending && !dados && (
        <p role="status" className="text-sm text-muted-foreground">
          Carregando catálogo…
        </p>
      )}

      {status === 400 && (
        <p role="alert" className="text-sm text-primary">
          Algum filtro é inválido. Revise ou limpe os filtros.
        </p>
      )}

      {skins.isError && status !== 400 && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar o catálogo. Tente novamente.
        </p>
      )}

      {dados && (
        <>
          <p className="text-sm text-muted-foreground">
            {`${dados.count} ${dados.count === 1 ? "skin" : "skins"}`}
          </p>
          {dados.results.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma skin encontrada.</p>
          ) : (
            <ul aria-label="Skins do catálogo" className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {dados.results.map((skin: CatalogSkin) => (
                <SkinCard key={skin.id} skin={skin} />
              ))}
            </ul>
          )}
          {dados.count > 0 && (
            <SkinsPagination
              pagina={pagina}
              count={dados.count}
              next={dados.next}
              previous={dados.previous}
              onPageChange={(page) => ir({ ...consulta, page })}
            />
          )}
        </>
      )}
    </main>
  );
}