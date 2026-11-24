import type { InventoryQuery } from "../../services/inventory";

/** A ordenação padrão do servidor: quando é a escolhida, nem vai na query. */
export const DEFAULT_ORDERING = "-acquired_at";

/**
 * Os desgastes que a API aceita no filtro, do mais novo ao mais usado
 * (backend/apps/inventory/rules.py, `WEARS`, lido em 2026-11-24). Só os rótulos: o desgaste de
 * cada item vem pronto do servidor.
 */
export const WEARS = [
  "Factory New",
  "Minimal Wear",
  "Field-Tested",
  "Well-Worn",
  "Battle-Scarred",
] as const;

/** As ordenações que a API aceita (apps/inventory/selectors.py, `ORDERING_CHOICES`, lido em 2026-11-24). */
export const ORDENACOES = [
  { value: "-acquired_at", label: "Mais recentes" },
  { value: "acquired_at", label: "Mais antigos" },
  { value: "-price", label: "Maior preço" },
  { value: "price", label: "Menor preço" },
  { value: "name", label: "Nome (A a Z)" },
  { value: "-name", label: "Nome (Z a A)" },
  { value: "float_value", label: "Menor float" },
  { value: "-float_value", label: "Maior float" },
] as const;

const texto = (valor: string | null | undefined) => valor?.trim() || undefined;

/** Tira espaços, descarta o vazio e o que vale por padrão (ordenação padrão, página 1). */
export function normalizar(consulta: InventoryQuery): InventoryQuery {
  const ordering = texto(consulta.ordering);
  const page = consulta.page;
  return {
    rarity: texto(consulta.rarity),
    weapon: texto(consulta.weapon),
    wear: texto(consulta.wear),
    q: texto(consulta.q),
    ordering: ordering === DEFAULT_ORDERING ? undefined : ordering,
    page: page !== undefined && Number.isInteger(page) && page > 1 ? page : undefined,
  };
}

/** A consulta que a barra de endereço descreve. Valor estranho segue adiante: quem decide se é
 * válido é o servidor (400), e a tela sabe lidar com isso. */
export function lerConsulta(params: URLSearchParams): InventoryQuery {
  const pagina = params.get("page");
  return normalizar({
    rarity: params.get("rarity") ?? undefined,
    weapon: params.get("weapon") ?? undefined,
    wear: params.get("wear") ?? undefined,
    q: params.get("q") ?? undefined,
    ordering: params.get("ordering") ?? undefined,
    page: pagina === null || pagina.trim() === "" ? undefined : Number(pagina),
  });
}
