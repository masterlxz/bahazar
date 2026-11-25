import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockFetch, type MockHandler } from "../../../test/fetchMock";
import { FACETS_KEY } from "../useSkins";
import { Filtros } from "../components/SkinsFilters";
import { renderComponent } from "../../../test/renderApp";

describe("SkinsFilters: select das facets", () => {
  const facets = {
    rarities: ["Consumer Grade", "Industrial Grade", "Mil-Spec Grade", "Restricted", "Classified", "Covert", "Contraband"],
    weapons: ["AK-47", "AWP", "Glock-18", "M4A4", "P250"],
    collections: ["Phoenix", "Dust", "Chroma", "Gamma"],
    wears: ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"],
  };

  function simularFacets(rotas: Record<string, MockHandler>) {
    return mockFetch({
      [FACETS_KEY.join("/")]: { status: 200, body: facets },
      ...rotas,
    });
  }

  it("renderiza selects com opções vindas das facets (raridade, arma, coleção, desgaste)", async () => {
    simularFacets({});
    renderComponent(<Filtros consulta={{}} facets={facets} onAplicar={() => {}} onLimpar={() => {}} />);

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());

    const raridade = within(screen.getByLabelText("Raridade")).getAllByRole("option");
    expect(raridade.map((o) => o.textContent)).toEqual([
      "Todas",
      "Consumer Grade",
      "Industrial Grade",
      "Mil-Spec Grade",
      "Restricted",
      "Classified",
      "Covert",
      "Contraband",
    ]);

    const arma = within(screen.getByLabelText("Arma")).getAllByRole("option");
    expect(arma.map((o) => o.textContent)).toEqual(["Todas", "AK-47", "AWP", "Glock-18", "M4A4", "P250"]);

    const colecao = within(screen.getByLabelText("Coleção")).getAllByRole("option");
    expect(colecao.map((o) => o.textContent)).toEqual(["Todas", "Phoenix", "Dust", "Chroma", "Gamma"]);

    const desgaste = within(screen.getByLabelText("Desgaste")).getAllByRole("option");
    expect(desgaste.map((o) => o.textContent)).toEqual([
      "Todos",
      "Factory New",
      "Minimal Wear",
      "Field-Tested",
      "Well-Worn",
      "Battle-Scarred",
    ]);
  });

  it("valores da consulta pré-preenchem os selects", async () => {
    simularFacets({});
    const consulta = {
      rarity: "Classified",
      weapon: "AWP",
      collection: "Phoenix",
      wear: "Field-Tested",
      q: "redline",
      ordering: "-price",
    };
    renderComponent(<Filtros consulta={consulta} facets={facets} onAplicar={() => {}} onLimpar={() => {}} />);

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());

    expect(screen.getByLabelText("Raridade")).toHaveValue("Classified");
    expect(screen.getByLabelText("Arma")).toHaveValue("AWP");
    expect(screen.getByLabelText("Coleção")).toHaveValue("Phoenix");
    expect(screen.getByLabelText("Desgaste")).toHaveValue("Field-Tested");
    expect(screen.getByLabelText("Buscar por nome")).toHaveValue("redline");
    expect(screen.getByLabelText("Ordenar por")).toHaveValue("-price");
  });

  it("valor da URL que não é opção do select (editado à mão) começa como 'Todas/Todos'", async () => {
    simularFacets({});
    const consulta = { rarity: "Inexistente", weapon: "AK-47" };
    renderComponent(<Filtros consulta={consulta} facets={facets} onAplicar={() => {}} onLimpar={() => {}} />);

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());
    expect(screen.getByLabelText("Raridade")).toHaveValue("");
    expect(screen.getByLabelText("Arma")).toHaveValue("AK-47");
  });

  it("Aplicar envia a consulta com todos os filtros (rarity, weapon, collection, wear, q, ordering)", async () => {
    let recebida: unknown = null;
    simularFacets({});
    renderComponent(<Filtros
      consulta={{}}
      facets={facets}
      onAplicar={(c) => {
        recebida = c;
      }}
      onLimpar={() => {}}
    />);

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Raridade"), { target: { value: "Covert" } });
    fireEvent.change(screen.getByLabelText("Arma"), { target: { value: "AWP" } });
    fireEvent.change(screen.getByLabelText("Coleção"), { target: { value: "Phoenix" } });
    fireEvent.change(screen.getByLabelText("Desgaste"), { target: { value: "Factory New" } });
    fireEvent.change(screen.getByLabelText("Buscar por nome"), { target: { value: "  asiimov  " } });
    fireEvent.change(screen.getByLabelText("Ordenar por"), { target: { value: "name" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    await waitFor(() => expect(recebida).toEqual({
      rarity: "Covert",
      weapon: "AWP",
      collection: "Phoenix",
      wear: "Factory New",
      q: "asiimov",
      ordering: "name",
    }));
  });

  it("busca aceita no máximo 50 caracteres", async () => {
    simularFacets({});
    renderComponent(<Filtros consulta={{}} facets={facets} onAplicar={() => {}} onLimpar={() => {}} />);

    await waitFor(() => expect(screen.getByLabelText("Buscar por nome")).toBeInTheDocument());
    expect(screen.getByLabelText("Buscar por nome")).toHaveAttribute("maxlength", "50");
  });

  it("Limpar filtros chama onLimpar", async () => {
    let limpou = false;
    simularFacets({});
    renderComponent(<Filtros consulta={{}} facets={facets} onAplicar={() => {}} onLimpar={() => { limpou = true; }} />);

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));
    expect(limpou).toBe(true);
  });
});