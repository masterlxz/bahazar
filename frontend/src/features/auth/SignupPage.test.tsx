import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  ERRO_USERNAME_EXISTE,
  ME,
  ME_OK,
  SENHA,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  SIGNUP,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

function preencherEEnviar() {
  fireEvent.change(screen.getByLabelText("Nome de usuário"), { target: { value: "ana_01" } });
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "ana@exemplo.com" } });
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: SENHA } });
  fireEvent.click(screen.getByRole("button", { name: "Criar conta" }));
}

describe("SignupPage", () => {
  it("envia { username, email, password } e leva ao perfil", async () => {
    let logado = false;
    const m = mockFetch({
      [SESSION]: () =>
        logado
          ? { status: 200, body: SESSION_AUTENTICADA }
          : { status: 401, body: SESSION_ANONIMA },
      [SIGNUP]: () => {
        logado = true;
        return { status: 200, body: SESSION_AUTENTICADA };
      },
      [ME]: { status: 200, body: ME_OK },
    });
    renderApp("/cadastrar");

    preencherEEnviar();

    await waitFor(() => expect(m.callsTo(SIGNUP)).toHaveLength(1));
    expect(m.callsTo(SIGNUP)[0]!.body).toEqual({
      username: "ana_01",
      email: "ana@exemplo.com",
      password: SENHA,
    });
    expect(await screen.findByRole("heading", { name: "Seu perfil" })).toBeInTheDocument();
  });

  it("mostra o erro do servidor junto do campo (nome de usuário já existe)", async () => {
    mockFetch({
      [SESSION]: { status: 401, body: SESSION_ANONIMA },
      [SIGNUP]: { status: 400, body: ERRO_USERNAME_EXISTE },
    });
    renderApp("/cadastrar");

    preencherEEnviar();

    expect(
      await screen.findByText("Já existe um jogador com esse nome de usuário."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Nome de usuário")).toHaveAttribute("aria-invalid", "true");
  });
});
