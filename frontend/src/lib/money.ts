const USD = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });

/**
 * Formata centavos de USD (ex.: 10000 → "US$ 100,00"). Só exibição: o saldo e os valores vêm
 * do servidor como inteiros, e o cliente nunca faz conta de dinheiro (GUIDELINES 1 e 11).
 */
export function formatUsd(centavos: number): string {
  if (!Number.isInteger(centavos)) {
    throw new RangeError(`Dinheiro é inteiro em centavos, recebido: ${centavos}`);
  }
  return USD.format(centavos / 100);
}
