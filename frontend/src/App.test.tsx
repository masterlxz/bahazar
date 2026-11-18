import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("mostra o nome do jogo como título principal", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1, name: "bahazar" })).toBeInTheDocument();
  });

  it("mostra as sete cores de raridade do catálogo", () => {
    render(<App />);

    expect(screen.getAllByTestId("rarity-chip")).toHaveLength(7);
  });
});
