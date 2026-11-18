import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  ERRO_LOGIN,
  LOGIN,
  ME,
  ME_OK,
  SENHA,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

function simular(loginStatus: number) {
  let logado = false;
  return mockFetch({
    [SESSION]: () =>
      logado
        ? { status: 200, body: SESSION_AUTENTICADA }
        : { status: 401, body: SESSION_ANONIMA },
    [LOGIN]: () => {
      if (loginStatus === 200) logado = true;
      return loginStatus === 200
        ? { status: 200, body: SESSION_AUTENTICADA }
        : { status: loginStatus, body: ERRO_LOGIN };
    },
    [ME]: { status: 200, body: ME_OK },
  });
}

function preencherEEnviar(identificador: string) {
  fireEvent.change(screen.getByLabelText("Usuário ou e-mail"), {
    target: { value: identificador },
  });
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: SENHA } });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("LoginPage", () => {
  it("entra com nome de usuário: envia { username, password }", async () => {
    const m = simular(200);
    renderApp("/entrar");

    preencherEEnviar("ana_01");

    await waitFor(() => expect(m.callsTo(LOGIN)).toHaveLength(1));
    expect(m.callsTo(LOGIN)[0]!.body).toEqual({ username: "ana_01", password: SENHA });
  });

  it("entra com e-mail: envia { email, password }", async () => {
    const m = simular(200);
    renderApp("/entrar");

    preencherEEnviar("ana@exemplo.com");

    await waitFor(() => expect(m.callsTo(LOGIN)).toHaveLength(1));
    expect(m.callsTo(LOGIN)[0]!.body).toEqual({ email: "ana@exemplo.com", password: SENHA });
  });

  it("login recusado mostra uma mensagem única, sem dizer se o usuário existe", async () => {
    simular(400);
    renderApp("/entrar");

    preencherEEnviar("ana_01");

    expect(await screen.findByRole("alert")).toHaveTextContent("Usuário ou senha incorretos");
  });

  it("login com sucesso leva ao perfil", async () => {
    simular(200);
    renderApp("/entrar");

    preencherEEnviar("ana_01");

    expect(await screen.findByRole("heading", { name: "Seu perfil" })).toBeInTheDocument();
  });
});
