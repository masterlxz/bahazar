import { useState, type FormEvent, type ReactNode } from "react";
import type { CatalogFacets } from "../../../types/api";
import type { CatalogQuery } from "../../../services/skins";

import { Button } from "../../../components/ui/button";
import { DEFAULT_ORDERING, ORDENACOES } from "../consulta";

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
  consulta: CatalogQuery;
  facets: CatalogFacets;
  onAplicar: (consulta: CatalogQuery) => void;
  onLimpar: () => void;
}

/** Os filtros ficam num rascunho local e só valem ao clicar em Aplicar (uma requisição por vez,
 * não uma por tecla). O `key` do chamador recria o rascunho quando a URL muda. */
export function Filtros({ consulta, facets, onAplicar, onLimpar }: FiltrosProps) {
  const [rarity, setRarity] = useState(consulta.rarity ?? "");
  const [weapon, setWeapon] = useState(consulta.weapon ?? "");
  const [collection, setCollection] = useState(consulta.collection ?? "");
  const [wear, setWear] = useState(consulta.wear ?? "");
  const [q, setQ] = useState(consulta.q ?? "");
  const [ordering, setOrdering] = useState<string>(
    ORDENACOES.find((o) => o.value === consulta.ordering)?.value ?? DEFAULT_ORDERING,
  );

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
          {facets.rarities.map((r) => (
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
          {facets.weapons.map((w) => (
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
          {facets.collections.map((c) => (
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
          {facets.wears.map((w) => (
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