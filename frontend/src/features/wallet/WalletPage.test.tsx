import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  DAILY,
  DAILY_RESGATADA,
  ERRO_DIARIA_NAO_LIBERADA,
  LOGOUT,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  WALLET,
  WALLET_AGUARDANDO,
  WALLET_PODE_RESGATAR,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";
import { WALLET_KEY } from "./useWallet";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

const RESGATAR = /Resgatar US\$\s10,00/;

/** Servidor simulado com estado: depois do resgate, a carteira passa a ser a "aguardando". */
function simularLogado(opcoes: { esperaDoResgate?: Promise<unknown> } = {}) {
  let carteira: unknown = WALLET_PODE_RESGATAR;
  let logado = true;
  return mockFetch({
    [SESSION]: () =>
      logado
        ? { status: 200, body: SESSION_AUTENTICADA }
        : { status: 401, body: SESSION_ANONIMA },
    [LOGOUT]: () => {
      logado = false;
      return { status: 401, body: SESSION_ANONIMA };
    },
    [WALLET]: () => ({ status: 200, body: carteira }),
    [DAILY]: () => {
      carteira = WALLET_AGUARDANDO;
      return { status: 201, body: DAILY_RESGATADA, wait: opcoes.esperaDoResgate };
    },
  });
}

describe("WalletPage", () => {
  it("sem sessão, /carteira redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/carteira");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sua carteira" })).not.toBeInTheDocument();
  });

  it("com sessão, mostra o saldo em US$ e o botão com o valor da diária", async () => {
    simularLogado();

    renderApp("/carteira");

    expect(await screen.findByRole("heading", { name: "Sua carteira" })).toBeInTheDocument();
    expect(await screen.findByTestId("saldo")).toHaveTextContent(/US\$\s100,00/);
    expect(screen.getByRole("button", { name: RESGATAR })).toBeEnabled();
    expect(screen.getByText(/Dia 1 da sequência/)).toBeInTheDocument();
  });

  it("o link Carteira aparece no cabeçalho só com sessão", async () => {
    simularLogado();
    renderApp("/carteira");
    expect(await screen.findByRole("link", { name: "Carteira" })).toBeInTheDocument();
  });

  it("clicar em Resgatar faz um POST com token CSRF e mostra o que foi recebido", async () => {
    const m = simularLogado();
    renderApp("/carteira");
    fireEvent.click(await screen.findByRole("button", { name: RESGATAR }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      /Você recebeu US\$\s10,00 \(dia 1\)/,
    );
    expect(m.callsTo(DAILY)).toHaveLength(1);
    expect(m.callsTo(DAILY)[0]!.headers["X-CSRFToken"]).toBe("tok");
    // O valor nunca sai do navegador: o corpo do POST é vazio.
    expect(m.callsTo(DAILY)[0]!.body).toBeUndefined();
    // O saldo novo vem do servidor (refetch), não de uma conta feita no cliente.
    await waitFor(() => expect(screen.getByTestId("saldo")).toHaveTextContent(/US\$\s110,00/));
    // Já resgatou hoje: o botão passa a anunciar a diária de amanhã (US$ 20,00) e fica bloqueado.
    expect(screen.getByRole("button", { name: /Resgatar US\$\s20,00/ })).toBeDisabled();
    expect(screen.getByText(/Disponível a partir de/)).toHaveTextContent(/24\/11\/2026/);
  });

  it("enquanto o resgate está pendente o botão fica desabilitado e o clique extra não envia outro POST", async () => {
    let liberar: () => void = () => {};
    const espera = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    const m = simularLogado({ esperaDoResgate: espera });
    renderApp("/carteira");
    const botao = await screen.findByRole("button", { name: RESGATAR });

    fireEvent.click(botao);
    await waitFor(() => expect(screen.getByRole("button", { name: /Resgatando/ })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: /Resgatando/ }));
    fireEvent.click(screen.getByRole("button", { name: /Resgatando/ }));

    liberar();
    await screen.findByRole("status");
    expect(m.callsTo(DAILY)).toHaveLength(1);
  });

  it("com a diária ainda bloqueada, mostra quando libera e o botão não faz nada", async () => {
    const m = mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [WALLET]: { status: 200, body: WALLET_AGUARDANDO },
    });

    renderApp("/carteira");

    expect(await screen.findByText(/Disponível a partir de/)).toHaveTextContent(/24\/11\/2026/);
    const botao = screen.getByRole("button", { name: /Resgatar/ });
    expect(botao).toBeDisabled();
    fireEvent.click(botao);
    expect(m.callsTo(DAILY)).toHaveLength(0);
  });

  it("409 daily_not_ready (outra aba resgatou): avisa, mostra quando libera e recarrega a carteira", async () => {
    let outraAbaResgatou = false;
    const m = mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [WALLET]: () => ({
        status: 200,
        body: outraAbaResgatou ? WALLET_AGUARDANDO : WALLET_PODE_RESGATAR,
      }),
      [DAILY]: () => {
        outraAbaResgatou = true;
        return { status: 409, body: ERRO_DIARIA_NAO_LIBERADA };
      },
    });
    renderApp("/carteira");
    fireEvent.click(await screen.findByRole("button", { name: RESGATAR }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Ainda não está disponível/);
    await waitFor(() => expect(m.callsTo(WALLET).length).toBeGreaterThanOrEqual(2));
    expect(await screen.findByText(/Disponível a partir de/)).toBeInTheDocument();
  });

  it("erro inesperado no resgate mostra mensagem própria, nunca o texto do servidor", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [WALLET]: { status: 200, body: WALLET_PODE_RESGATAR },
      [DAILY]: { status: 500, body: { code: "boom", message: "Traceback (most recent call last)" } },
    });
    renderApp("/carteira");
    fireEvent.click(await screen.findByRole("button", { name: RESGATAR }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Não foi possível resgatar a diária. Tente novamente.");
    expect(alerta).not.toHaveTextContent("Traceback");
  });

  it("falha ao carregar a carteira mostra erro e nenhum saldo", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [WALLET]: { status: 500 },
    });

    renderApp("/carteira");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar a carteira. Tente novamente.",
    );
    expect(screen.queryByTestId("saldo")).not.toBeInTheDocument();
  });

  it("ao sair, o saldo de quem saiu é removido do cache (não vaza para o próximo usuário)", async () => {
    simularLogado();
    const { client } = renderApp("/carteira");
    await screen.findByTestId("saldo");
    expect(client.getQueryData(WALLET_KEY)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await screen.findByRole("heading", { name: "Entrar" });
    expect(client.getQueryData(WALLET_KEY)).toBeUndefined();
  });
});
