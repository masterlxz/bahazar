/** Data e hora curtas no fuso do navegador, em pt-BR (ex.: "24/11/2026 12:00"). */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}
