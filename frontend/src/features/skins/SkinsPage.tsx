import { useSearchParams } from "react-router";

import { AtribuicaoSkinport } from "../../components/AtribuicaoSkinport";
import { ApiError } from "../../services/http";
import { catalogParams } from "../../services/skins";
import type { CatalogQuery } from "../../services/skins";
import { lerConsulta, normalizar } from "./consulta";
import { useSkins, useFacets } from "./useSkins";
import { SkinCard } from "./components/SkinCard";
import { Filtros } from "./components/SkinsFilters";
import { Pagination } from "./components/SkinsPagination";

const FILTRO_INVALIDO = "Algum filtro é inválido. Revise ou limpe os filtros.";
const FALHOU = "Não foi possível carregar o catálogo. Tente novamente.";

export default function SkinsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const consulta = lerConsulta(searchParams);
  const pagina = consulta.page ?? 1;

  const skins = useSkins(consulta);
  const facets = useFacets();

  const ir = (nova: CatalogQuery) => setSearchParams(catalogParams(normalizar(nova)));
  const status = skins.error instanceof ApiError ? skins.error.status : null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Catálogo de Skins</h1>

      {facets.isSuccess && (
        <Filtros
          key={`${searchParams.toString()}`}
          consulta={consulta}
          facets={facets.data}
          onAplicar={ir}
          onLimpar={() => ir({})}
        />
      )}

      {skins.isPending && (
        <p role="status" className="text-sm text-muted-foreground">
          Carregando catálogo…
        </p>
      )}

      {status === 400 && (
        <p role="alert" className="text-sm text-primary">
          {FILTRO_INVALIDO}
        </p>
      )}

      {skins.isError && status !== 400 && (
        <p role="alert" className="text-sm text-primary">
          {FALHOU}
        </p>
      )}

      {skins.isSuccess && (
        <>
          <p className="text-sm text-muted-foreground">
            {`${skins.data.count} ${skins.data.count === 1 ? "skin" : "skins"}`}
          </p>
          {skins.data.results.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma skin encontrada.</p>
          ) : (
            <ul aria-label="Skins do catálogo" className="grid gap-3 sm:grid-cols-2">
              {skins.data.results.map((skin) => (
                <SkinCard key={skin.id} skin={skin} />
              ))}
            </ul>
          )}
          {skins.data.results.length < 0 && <AtribuicaoSkinport />}
          <Pagination
            dados={skins.data}
            pagina={pagina}
            consulta={consulta}
            onMudarPagina={ir}
          />
        </>
      )}
    </main>
  );
}