import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  LOGOUT,
  ME,
  ME_OK,
  ME_PATCH,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

function simularLogado() {
  let logado = true;
  return mockFetch({
    [SESSION]: () =>
      logado
        ? { status: 200, body: SESSION_AUTENTICADA }
        : { status: 401, body: SESSION_ANONIMA },
    [LOGOUT]: () => {
      logado = false;
      // O allauth responde 401 ao fazer logout com sucesso (a sessão deixou de existir).
      return { status: 401, body: SESSION_ANONIMA };
    },
    [ME]: { status: 200, body: ME_OK },
    [ME_PATCH]: (call) => ({
      status: 200,
      body: { ...ME_OK, avatar: (call.body as { avatar: string }).avatar },
    }),
  });
}

describe("ProfilePage", () => {
  it("sem sessão, /perfil redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/perfil");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Seu perfil" })).not.toBeInTheDocument();
  });

  it("com sessão, mostra usuário, e-mail e os 8 avatares (o atual marcado)", async () => {
    simularLogado();

    renderApp("/perfil");

    expect(await screen.findByRole("heading", { name: "Seu perfil" })).toBeInTheDocument();
    expect(await screen.findByText("ana@exemplo.com")).toBeInTheDocument();
    expect(screen.getByText("ana_01")).toBeInTheDocument();
    expect(await screen.findAllByRole("radio")).toHaveLength(8);
    expect(screen.getByRole("radio", { name: "Avatar default" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("clicar num avatar faz PATCH com token CSRF e atualiza a tela", async () => {
    const m = simularLogado();
    renderApp("/perfil");
    const ember = await screen.findByRole("radio", { name: "Avatar ember" });

    fireEvent.click(ember);

    await waitFor(() => expect(m.callsTo(ME_PATCH)).toHaveLength(1));
    const chamada = m.callsTo(ME_PATCH)[0]!;
    expect(chamada.body).toEqual({ avatar: "ember" });
    expect(chamada.headers["X-CSRFToken"]).toBe("tok");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Avatar ember" })).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );
  });

  it("Sair faz DELETE da sessão e, numa página protegida, leva ao login", async () => {
    const m = simularLogado();
    renderApp("/perfil");
    await screen.findByRole("heading", { name: "Seu perfil" });

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await waitFor(() => expect(m.callsTo(LOGOUT)).toHaveLength(1));
    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Seu perfil" })).not.toBeInTheDocument();
  });

  it("depois de sair, o perfil do usuário anterior não sobra em cache", async () => {
    simularLogado();
    renderApp("/perfil");
    await screen.findByText("ana@exemplo.com");

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await screen.findByRole("heading", { name: "Entrar" });
    expect(screen.queryByText("ana@exemplo.com")).not.toBeInTheDocument();
  });
});
