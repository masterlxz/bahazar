import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("renderiza um <button> acessível com o texto", () => {
    render(<Button>Comprar</Button>);

    expect(screen.getByRole("button", { name: "Comprar" })).toBeInTheDocument();
  });

  it("chama onClick ao clicar", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Comprar</Button>);

    fireEvent.click(screen.getByRole("button", { name: "Comprar" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("não dispara onClick quando desabilitado", () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Comprar
      </Button>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Comprar" }));

    expect(onClick).not.toHaveBeenCalled();
  });

  it("aplica o destaque vermelho (primary) por padrão", () => {
    render(<Button>Comprar</Button>);

    expect(screen.getByRole("button")).toHaveClass("bg-primary");
  });
});
