import { describe, expect, it } from "vitest";

import { formatUsd } from "./money";

/** O `Intl` separa "US$" do número com espaço não separável; o teste compara com espaço comum. */
const normal = (texto: string) => texto.replace(/ /g, " ");

describe("formatUsd", () => {
  it.each([
    [0, "US$ 0,00"],
    [1, "US$ 0,01"],
    [99, "US$ 0,99"],
    [100, "US$ 1,00"],
    [1_000, "US$ 10,00"],
    [10_000, "US$ 100,00"],
    [123_456_789, "US$ 1.234.567,89"],
  ])("%i centavos viram %s", (centavos, esperado) => {
    expect(normal(formatUsd(centavos))).toBe(esperado);
  });

  it.each([1.5, 0.1, Number.NaN, Number.POSITIVE_INFINITY])(
    "recusa %s: dinheiro é sempre inteiro em centavos",
    (invalido) => {
      expect(() => formatUsd(invalido)).toThrow(RangeError);
    },
  );
});
