import { useState, type FormEvent, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router";

import { Button } from "../../components/ui/button";
import { formatDateTime } from "../../lib/datetime";
import { formatUsd } from "../../lib/money";
import { ApiError } from "../../services/http";
import { inventoryParams, type InventoryQuery } from "../../services/inventory";
import type { InventoryItem } from "../../types/api";
import type { CatalogFacets } from "../../types/api";
import { DEFAULT_ORDERING, ORDENACOES, lerConsulta, normalizar, opcoesRarity, opcoesWeapon, opcoesCollection, opcoesWear } from "./consulta";
import { useInventory, useInventoryFacets, usernameImpossivel } from "./useInventory";

// Uma mensagem só para "não pode ver" (não amigo, pedido pendente, bloqueado ou inexistente): o
// servidor devolve o mesmo 404 para todos, e a tela não pode distingui-los (ADR 0010).
const NAO_ENCONTRADO = "Inventário não encontrado.";
const FILTRO_INVALIDO = "Algum filtro é inválido. Revise ou limpe os filtros.";
const FALHOU = "Não foi possível carregar o inventário. Tente novamente.";

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

interface FiltrosProps {
  consulta: InventoryQuery;
  facets: CatalogFacets | undefined;
  onAplicar: (consulta: InventoryQuery) => void;
  onLimpar: () => void;
}

/** Os filtros ficam num rascunho local e só valem ao clicar em Aplicar (uma requisição por vez,
 * não uma por tecla). O `key` do chamador recria o rascunho quando a URL muda. */
function Filtros({ consulta, facets, onAplicar, onLimpar }: FiltrosProps) {
  const [rarity, setRarity] = useState(consulta.rarity ?? "");
  const [weapon, setWeapon] = useState(consulta.weapon ?? "");
  const [collection, setCollection] = useState(consulta.collection ?? "");
  const [wear, setWear] = useState(consulta.wear ?? "");
  const [q, setQ] = useState(consulta.q ?? "");
  const [ordering, setOrdering] = useState<string>(
    ORDENACOES.find((o) => o.value === consulta.ordering)?.value ?? DEFAULT_ORDERING,
  );

  const raridades = opcoesRarity(facets);
  const armas = opcoesWeapon(facets);
  const colecoes = opcoesCollection(facets);
  const desgastes = opcoesWear(facets);

  function aplicar(evento: FormEvent) {
    evento.preventDefault();
    onAplicar({ rarity, weapon, collection, wear, q, ordering });
  }

  return (
    <form
      onSubmit={aplicar}
      className="grid gap-4 rounded-lg border border-border bg-card p-6 sm:grid-cols-2 lg:grid-cols-3"
    >
      <Campo id="filtro-raridade" rotulo="Raridade">
        <select
          id="filtro-raridade"
          value={rarity}
          onChange={(e) => setRarity(e.target.value)}
          className={CLASSE_CAMPO}
        >
          <option value="">Todas</option>
          {raridades.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </Campo>
      <Campo id="filtro-arma" rotulo="Arma">
        <select
          id="filtro-arma"
          value={weapon}
          onChange={(e) => setWeapon(e.target.value)}
          className={CLASSE_CAMPO}
        >
          <option value="">Todas</option>
          {armas.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </Campo>
      <Campo id="filtro-colecao" rotulo="Coleção">
        <select
          id="filtro-colecao"
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
          className={CLASSE_CAMPO}
        >
          <option value="">Todas</option>
          {colecoes.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Campo>
      <Campo id="filtro-desgaste" rotulo="Desgaste">
        <select
          id="filtro-desgaste"
          value={wear}
          onChange={(e) => setWear(e.target.value)}
          className={CLASSE_CAMPO}
        >
          <option value="">Todos</option>
          {desgastes.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </Campo>
      <Campo id="filtro-busca" rotulo="Buscar por nome">
        <input
          id="filtro-busca"
          value={q}
          maxLength={50}
          onChange={(e) => setQ(e.target.value)}
          className={CLASSE_CAMPO}
        />
      </Campo>
      <Campo id="filtro-ordenacao" rotulo="Ordenar por">
        <select
          id="filtro-ordenacao"
          value={ordering}
          onChange={(e) => setOrdering(e.target.value)}
          className={CLASSE_CAMPO}
        >
          {ORDENACOES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Campo>
      <div className="flex items-end gap-2 lg:col-span-3">
        <Button type="submit">Aplicar</Button>
        <Button type="button" variant="outline" onClick={onLimpar}>
          Limpar filtros
        </Button>
      </div>
    </form>
  );
}

function Item({ item }: { item: InventoryItem }) {
  const { skin } = item;
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4">
      <span className="font-semibold">{skin.name}</span>
      <span className="text-sm">{skin.weapon}</span>
      <span className="text-sm text-muted-foreground">{skin.rarity}</span>
      {skin.collection && (
        <span className="text-sm text-muted-foreground">{skin.collection}</span>
      )}
      <span className="text-sm">{item.wear}</span>
      <span className="text-sm text-muted-foreground">{`Float ${item.float_value}`}</span>
      <span className="font-semibold">{formatUsd(item.reference_price)}</span>
      <span className="text-xs text-muted-foreground">
        {`Adquirido em ${formatDateTime(item.acquired_at)}`}
      </span>
    </li>
  );
}

export default function InventoryPage() {
  const { username } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const consulta = lerConsulta(searchParams);
  const pagina = consulta.page ?? 1;
  const inventario = useInventory(username, consulta);
  const facets = useInventoryFacets();

  // A consulta mora na URL: voltar do navegador desfaz um filtro, e o link é compartilhável.
  const ir = (nova: InventoryQuery) => setSearchParams(inventoryParams(normalizar(nova)));
  const status = inventario.error instanceof ApiError ? inventario.error.status : null;
  const naoEncontrado = usernameImpossivel(username) || status === 404;
  // Só um sucesso mostra itens. Um refetch que falha (ex.: o amigo me desfez e agora é 404) MANTÉM
  // `data` no TanStack Query; usar `inventario.data` aqui exibiria o inventário antigo dele junto
  // com a mensagem de erro.
  const dados = inventario.isSuccess ? inventario.data : null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">
        {username === undefined ? "Inventário" : `Inventário de ${username}`}
      </h1>

      <Filtros
        key={`${username ?? ""}?${searchParams.toString()}`}
        consulta={consulta}
        facets={facets.data}
        onAplicar={ir}
        onLimpar={() => ir({})}
      />

      {inventario.isPending && !naoEncontrado && (
        <p role="status" className="text-sm text-muted-foreground">
          Carregando inventário…
        </p>
      )}

      {naoEncontrado && (
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="text-sm text-primary">
            {NAO_ENCONTRADO}
          </p>
          {pagina > 1 && (
            <Button variant="outline" onClick={() => ir({ ...consulta, page: undefined })}>
              Voltar à primeira página
            </Button>
          )}
        </div>
      )}
      {status === 400 && (
        <p role="alert" className="text-sm text-primary">
          {FILTRO_INVALIDO}
        </p>
      )}
      {inventario.isError && !naoEncontrado && status !== 400 && (
        <p role="alert" className="text-sm text-primary">
          {FALHOU}
        </p>
      )}

      {dados && (
        <>
          <p className="text-sm text-muted-foreground">
            {`${dados.count} ${dados.count === 1 ? "item" : "itens"}`}
          </p>
          {dados.results.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum item encontrado.</p>
          ) : (
            <ul aria-label="Itens do inventário" className="grid gap-3 sm:grid-cols-2">
              {dados.results.map((item) => (
                <Item key={item.id} item={item} />
              ))}
            </ul>
          )}
          {dados.results.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Preço de referência via{" "}
              <a
                href="https://skinport.com"
                rel="noopener noreferrer"
                className="underline"
              >
                Skinport
              </a>
            </p>
          )}
          {dados.count > 0 && (
            <nav aria-label="Paginação" className="flex items-center justify-between gap-3">
              <Button
                variant="outline"
                disabled={dados.previous === null}
                onClick={() => ir({ ...consulta, page: pagina - 1 })}
              >
                Anterior
              </Button>
              <span className="text-sm">{`Página ${pagina}`}</span>
              <Button
                variant="outline"
                disabled={dados.next === null}
                onClick={() => ir({ ...consulta, page: pagina + 1 })}
              >
                Próxima
              </Button>
            </nav>
          )}
        </>
      )}
    </main>
  );
}
