import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmButton } from "./ConfirmButton";

function montar(props: { disabled?: boolean } = {}) {
  const onConfirm = vi.fn();
  render(<ConfirmButton label="Remover" name="carla_03" onConfirm={onConfirm} {...props} />);
  return onConfirm;
}

describe("ConfirmButton", () => {
  it("o primeiro clique só pede confirmação, não executa", () => {
    const onConfirm = montar();

    fireEvent.click(screen.getByRole("button", { name: "Remover carla_03" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirmar Remover carla_03" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar Remover carla_03" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remover carla_03" })).not.toBeInTheDocument();
  });

  it("confirmar executa uma vez e volta ao botão inicial", () => {
    const onConfirm = montar();
    fireEvent.click(screen.getByRole("button", { name: "Remover carla_03" }));

    fireEvent.click(screen.getByRole("button", { name: "Confirmar Remover carla_03" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Remover carla_03" })).toBeInTheDocument();
  });

  it("cancelar volta ao botão inicial sem executar", () => {
    const onConfirm = montar();
    fireEvent.click(screen.getByRole("button", { name: "Remover carla_03" }));

    fireEvent.click(screen.getByRole("button", { name: "Cancelar Remover carla_03" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Remover carla_03" })).toBeInTheDocument();
  });

  it("desabilitado, o botão não abre a confirmação", () => {
    const onConfirm = montar({ disabled: true });

    const botao = screen.getByRole("button", { name: "Remover carla_03" });
    fireEvent.click(botao);

    expect(botao).toBeDisabled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
