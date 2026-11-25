import { Button } from "../../../components/ui/button";

interface SkinsPaginationProps {
  pagina: number;
  count: number;
  next: string | null;
  previous: string | null;
  onPageChange: (page: number) => void;
}

export function SkinsPagination({ pagina, count, next, previous, onPageChange }: SkinsPaginationProps) {
  return (
    <nav aria-label="Paginação" className="flex items-center justify-between gap-3">
      <Button variant="outline" disabled={previous === null} onClick={() => onPageChange(pagina - 1)}>
        Anterior
      </Button>
      <span className="text-sm">{`Página ${pagina}`}</span>
      <Button variant="outline" disabled={next === null} onClick={() => onPageChange(pagina + 1)}>
        Próxima
      </Button>
    </nav>
  );
}