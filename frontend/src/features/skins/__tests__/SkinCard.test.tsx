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

  it("Consumer Grade → cinza", () => {
    const cinza = { ...skinBase, rarity: "Consumer Grade" as const };
    renderComponent(<SkinCard skin={cinza} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-neutral-500");
  });

  it("Industrial Grade → azul-claro", () => {
    const azulClaro = { ...skinBase, rarity: "Industrial Grade" as const };
    renderComponent(<SkinCard skin={azulClaro} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-sky-400");
  });

  it("Mil-Spec Grade → azul", () => {
    const azul = { ...skinBase, rarity: "Mil-Spec Grade" as const };
    renderComponent(<SkinCard skin={azul} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-blue-500");
  });

  it("Restricted → roxo", () => {
    const roxo = { ...skinBase, rarity: "Restricted" as const };
    renderComponent(<SkinCard skin={roxo} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-purple-500");
  });

  it("Classified → rosa", () => {
    const rosa = { ...skinBase, rarity: "Classified" as const };
    renderComponent(<SkinCard skin={rosa} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-pink-500");
  });

  it("Covert → vermelho", () => {
    const vermelho = { ...skinBase, rarity: "Covert" as const };
    renderComponent(<SkinCard skin={vermelho} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveClass("bg-red-500");
  });

  it("Contraband → laranja", () => {
    const laranja = { ...skinBase, rarity: "Contraband" as const };
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

  it("inicial da arma 'AWP' → 'A'", () => {
    const awp = { ...skinBase, weapon: "AWP" };
    renderComponent(<SkinCard skin={awp} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveTextContent("A");
  });

  it("inicial da arma 'Glock-18' → 'G'", () => {
    const glock = { ...skinBase, weapon: "Glock-18" };
    renderComponent(<SkinCard skin={glock} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveTextContent("G");
  });

  it("inicial da arma 'M4A4' → 'MA'", () => {
    const m4a4 = { ...skinBase, weapon: "M4A4" };
    renderComponent(<SkinCard skin={m4a4} />);
    expect(screen.getByRole("img", { name: /placeholder da skin redline/i })).toHaveTextContent("MA");
  });
});