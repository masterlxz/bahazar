import type { Paginated } from "../../../types/api";
import type { CatalogQuery } from "../../../services/skins";

import { Button } from "../../../components/ui/button";

interface PaginationProps {
  dados: Paginated<unknown>;
  pagina: number;
  consulta: CatalogQuery;
  onMudarPagina: (nova: CatalogQuery) => void;
}

export function Pagination({ dados, pagina, consulta, onMudarPagina }: PaginationProps) {
  if (dados.count === 0) return null;

  return (
    <nav aria-label="Paginação" className="flex items-center justify-between gap-3">
      <Button
        variant="outline"
        disabled={dados.previous === null}
        onClick={() => onMudarPagina({ ...consulta, page: pagina - 1 })}
      >
        Anterior
      </Button>
      <span className="text-sm">{`Página ${pagina}`}</span>
      <Button
        variant="outline"
        disabled={dados.next === null}
        onClick={() => onMudarPagina({ ...consulta, page: pagina + 1 })}
      >
        Próxima
      </Button>
    </nav>
  );
}