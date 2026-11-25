import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SkinCard } from "../components/SkinCard";
import { renderComponent } from "../../../test/renderApp";

describe("SkinCard: placeholder por raridade", () => {
  const skinBase = {
    id: "k1",
    name: "Redline",
    weapon: "AK-47",
    rarity: "Classified" as const,
    collection: "Phoenix",
    image_url: null,
    image_source: "none" as const,
  };

  it("mostra a inicial da arma no placeholder colorido pela raridade", () => {
    renderComponent(<SkinCard skin={skinBase} />);

    const placeholder = screen.getByRole("img", { name: /placeholder da skin redline/i });
    expect(placeholder).toHaveTextContent("AK");
    expect(placeholder).toHaveClass("bg-pink-500");
  });

  it("Consumer Grade → cinza, Industrial Grade → azul-claro, Mil-Spec Grade → azul", () => {
    const cinza = { ...skinBase, rarity: "Consumer Grade" as const };
    const azulClaro = { ...skinBase, rarity: "Industrial Grade" as const };
    const azul = { ...skinBase, rarity: "Mil-Spec Grade" as const };

    renderComponent(<SkinCard skin={cinza} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-neutral-500");

    renderComponent(<SkinCard skin={azulClaro} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-sky-400");

    renderComponent(<SkinCard skin={azul} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-blue-500");
  });

  it("Restricted → roxo, Classified → rosa, Covert → vermelho, Contraband → laranja", () => {
    const roxo = { ...skinBase, rarity: "Restricted" as const };
    const rosa = { ...skinBase, rarity: "Classified" as const };
    const vermelho = { ...skinBase, rarity: "Covert" as const };
    const laranja = { ...skinBase, rarity: "Contraband" as const };

    renderComponent(<SkinCard skin={roxo} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-purple-500");

    renderComponent(<SkinCard skin={rosa} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-pink-500");

    renderComponent(<SkinCard skin={vermelho} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-red-500");

    renderComponent(<SkinCard skin={laranja} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-orange-500");
  });

  it("raridade desconhecida cai no cinza neutro", () => {
    const desconhecida = { ...skinBase, rarity: "Raridade Inexistente" as const };
    renderComponent(<SkinCard skin={desconhecida} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-neutral-500");
  });

  it("mostra nome, arma, raridade e coleção quando presente", () => {
    renderComponent(<SkinCard skin={skinBase} />);
    expect(screen.getByText("Redline")).toBeInTheDocument();
    expect(screen.getByText("AK-47")).toBeInTheDocument();
    expect(screen.getByText("classified")).toBeInTheDocument();
    expect(screen.getByText("Phoenix")).toBeInTheDocument();
  });

  it("não mostra coleção quando vazia", () => {
    const semColecao = { ...skinBase, collection: "" };
    renderComponent(<SkinCard skin={semColecao} />);
    expect(screen.queryByText("Phoenix")).not.toBeInTheDocument();
  });

  it("inicial da arma com hífen e espaço: 'AWP' → 'A', 'Glock-18' → 'G', 'M4A4' → 'MA'", () => {
    const awp = { ...skinBase, weapon: "AWP" };
    const glock = { ...skinBase, weapon: "Glock-18" };
    const m4a4 = { ...skinBase, weapon: "M4A4" };

    renderComponent(<SkinCard skin={awp} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveTextContent("A");

    renderComponent(<SkinCard skin={glock} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveTextContent("G");

    renderComponent(<SkinCard skin={m4a4} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveTextContent("MA");
  });
});