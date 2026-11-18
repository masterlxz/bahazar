import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockFetch } from "./test/fetchMock";
import { SESSION, SESSION_ANONIMA } from "./test/fixtures";
import { renderApp } from "./test/renderApp";

describe("App (início)", () => {
  it("mostra o nome do jogo como título principal", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/");

    expect(await screen.findByRole("heading", { level: 1, name: "bahazar" })).toBeInTheDocument();
  });

  it("mostra as sete cores de raridade do catálogo", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/");

    expect(await screen.findAllByTestId("rarity-chip")).toHaveLength(7);
  });

  it("visitante vê os links Entrar e Cadastrar no cabeçalho", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/");

    expect(await screen.findByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/entrar");
    expect(screen.getByRole("link", { name: "Cadastrar" })).toHaveAttribute("href", "/cadastrar");
  });
});
