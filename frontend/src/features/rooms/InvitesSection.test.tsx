import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  CODIGO_DO_CONVITE,
  CONVITE_ATIVO,
  CONVITE_ESGOTADO,
  CONVITE_EXPIRADO,
  CONVITE_NOVO,
  CONVITE_REVOGADO,
  ERRO_LIMITE_DE_CONVITES,
  ERRO_POLITICA_DO_CONVITE,
  LOGOUT,
  MEMBROS_DA_S1,
  ROOMS,
  SALA_ADMIN,
  SALA_DONO,
  SALA_MEMBRO,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  createInviteRoute,
  invitesRoute,
  membersRoute,
  revokeInviteRoute,
  roomRoute,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";
import { invitesKey } from "./useRooms";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});
afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "clipboard"); // o jsdom não tem área de transferência
});

function simularAreaDeTransferencia(writeText: (texto: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
}

const secao = (nome: string) => screen.getByRole("region", { name: nome });
const TODOS = [CONVITE_ATIVO, CONVITE_EXPIRADO, CONVITE_ESGOTADO, CONVITE_REVOGADO];

/** Servidor simulado de UMA sala com convites; gerar e revogar mudam o estado. */
function simular(
  opcoes: {
    sala?: typeof SALA_DONO;
    convites?: unknown[];
    esperaDaCriacao?: Promise<unknown>;
  } = {},
) {
  const sala = opcoes.sala ?? SALA_DONO;
  let convites: unknown[] = opcoes.convites ?? TODOS;
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
    [ROOMS]: { status: 200, body: [sala] },
    [roomRoute(sala.id)]: { status: 200, body: sala },
    [membersRoute(sala.id)]: { status: 200, body: MEMBROS_DA_S1 },
    [invitesRoute(sala.id)]: () => ({ status: 200, body: convites }),
    [createInviteRoute(sala.id)]: () => {
      // A lista (GET) nunca traz o código: só a resposta da criação.
      const semCodigo: Record<string, unknown> = { ...CONVITE_NOVO };
      delete semCodigo.code;
      convites = [semCodigo, ...convites];
      return { status: 201, body: CONVITE_NOVO, wait: opcoes.esperaDaCriacao };
    },
    [revokeInviteRoute(sala.id, "i1")]: () => {
      convites = convites.map((c) =>
        (c as { id: string }).id === "i1"
          ? { ...(c as object), status: "revoked", revoked_at: "2026-11-24T12:00:00Z" }
          : c,
      );
      return { status: 204 };
    },
  });
}

async function abrir(opcoes: Parameters<typeof simular>[0] = {}) {
  const m = simular(opcoes);
  const app = renderApp(`/grupos/${(opcoes.sala ?? SALA_DONO).id}`);
  await screen.findByRole("region", { name: "Convites" });
  return { m, ...app };
}

describe("InvitesSection", () => {
  // --- quem vê -------------------------------------------------------------------------------

  it("o dono e o administrador veem a seção de convites", async () => {
    await abrir();
    expect(secao("Convites")).toBeInTheDocument();
  });

  it("o administrador também vê a seção", async () => {
    await abrir({ sala: SALA_ADMIN });
    expect(secao("Convites")).toBeInTheDocument();
  });

  it("o membro comum não vê a seção e a tela nem busca os convites", async () => {
    const m = simular({ sala: SALA_MEMBRO });
    renderApp("/grupos/s2");

    await screen.findByRole("heading", { name: "Time B" });
    await screen.findByText("2 de 20 membros");

    expect(screen.queryByRole("region", { name: "Convites" })).not.toBeInTheDocument();
    expect(m.callsTo(invitesRoute("s2"))).toHaveLength(0);
  });

  // --- lista -----------------------------------------------------------------------------------

  it("lista cada convite com o estado vindo do servidor, os usos e quando expira, sem código", async () => {
    await abrir();

    const lista = within(secao("Convites"));
    expect(await lista.findByText("Ativo")).toBeInTheDocument();
    expect(lista.getByText("Expirado")).toBeInTheDocument();
    expect(lista.getByText("Esgotado")).toBeInTheDocument();
    expect(lista.getByText("Revogado")).toBeInTheDocument();
    expect(lista.getByText("3 de 10 usos")).toBeInTheDocument();
    expect(lista.getAllByText(/Expira em .*30\/11\/2026/)).toHaveLength(4);
    expect(document.body).not.toHaveTextContent(CODIGO_DO_CONVITE);
  });

  it("só o convite Ativo tem o botão Revogar", async () => {
    await abrir();
    await within(secao("Convites")).findByText("Ativo");

    expect(screen.getAllByRole("button", { name: /^Revogar convite/ })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Revogar convite 1" })).toBeInTheDocument();
  });

  it("sem convites mostra uma mensagem em vez de ficar em branco", async () => {
    await abrir({ convites: [] });

    expect(await within(secao("Convites")).findByText("Nenhum convite ainda.")).toBeInTheDocument();
  });

  it("falha ao carregar os convites mostra um aviso", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [roomRoute("s1")]: { status: 200, body: SALA_DONO },
      [membersRoute("s1")]: { status: 200, body: MEMBROS_DA_S1 },
      [invitesRoute("s1")]: { status: 500 },
    });
    renderApp("/grupos/s1");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar os convites. Tente novamente.",
    );
  });

  // --- gerar -----------------------------------------------------------------------------------

  it("os campos vêm com o padrão de 7 dias e 10 usos, com a dica dos tetos", async () => {
    await abrir();

    expect(screen.getByLabelText("Validade (dias)")).toHaveValue(7);
    expect(screen.getByLabelText("Usos máximos")).toHaveValue(10);
    expect(screen.getByText("De 1 a 30 dias")).toBeInTheDocument();
    expect(screen.getByText("De 1 a 50 usos")).toBeInTheDocument();
  });

  it("gerar faz POST com o padrão e CSRF e mostra o código com o aviso", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));

    const novo = await screen.findByRole("region", { name: "Novo convite" });
    expect(within(novo).getByText(CODIGO_DO_CONVITE)).toBeInTheDocument();
    expect(
      within(novo).getByText("Guarde este código agora. Ele não será mostrado de novo."),
    ).toBeInTheDocument();
    const chamada = m.callsTo(createInviteRoute("s1"))[0]!;
    expect(chamada.body).toEqual({ expires_in_days: 7, max_uses: 10 });
    expect(chamada.headers["X-CSRFToken"]).toBe("tok");
  });

  it("gerar com valores próprios envia os valores digitados", async () => {
    const { m } = await abrir();
    fireEvent.change(screen.getByLabelText("Validade (dias)"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("Usos máximos"), { target: { value: "50" } });

    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));

    await screen.findByRole("region", { name: "Novo convite" });
    expect(m.callsTo(createInviteRoute("s1"))[0]!.body).toEqual({
      expires_in_days: 30,
      max_uses: 50,
    });
  });

  it("depois de gerar, a lista é recarregada e mostra o convite novo, sem o código", async () => {
    await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    await waitFor(() =>
      expect(within(secao("Convites")).getAllByText("Ativo").length).toBeGreaterThanOrEqual(2),
    );
    // "0 de 10 usos": o convite novo e o revogado da fixture (que nunca foi usado).
    expect(within(secao("Convites")).getAllByText("0 de 10 usos")).toHaveLength(2);
  });

  it.each([
    ["Validade (dias)", ""],
    ["Validade (dias)", "0"],
    ["Validade (dias)", "-1"],
    ["Validade (dias)", "1.5"],
    ["Usos máximos", ""],
    ["Usos máximos", "0"],
    ["Usos máximos", "2.5"],
  ])("com %s = '%s' o botão Gerar convite fica desabilitado", async (campo, valor) => {
    await abrir();

    fireEvent.change(screen.getByLabelText(campo), { target: { value: valor } });

    expect(screen.getByRole("button", { name: "Gerar convite" })).toBeDisabled();
  });

  it("enquanto o convite é gerado o botão fica desabilitado e o clique extra não gera outro", async () => {
    let liberar: () => void = () => {};
    const espera = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    const { m } = await abrir({ esperaDaCriacao: espera });

    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Gerar convite" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));

    liberar();
    await screen.findByRole("region", { name: "Novo convite" });
    expect(m.callsTo(createInviteRoute("s1"))).toHaveLength(1);
  });

  it.each([
    [409, ERRO_LIMITE_DE_CONVITES, "A sala já tem 10 convites ativos. Revogue um para gerar outro."],
    [400, ERRO_POLITICA_DO_CONVITE, "Use de 1 a 30 dias e de 1 a 50 usos."],
    [403, { detail: "Traceback (most recent call last)" }, "Só o dono ou um administrador pode gerar convites."],
    [500, { code: "boom", message: "Traceback (most recent call last)" }, "Não foi possível gerar o convite. Tente novamente."],
  ])("erro %i ao gerar mostra a mensagem própria, nunca o texto do servidor", async (status, corpo, mensagem) => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [roomRoute("s1")]: { status: 200, body: SALA_DONO },
      [membersRoute("s1")]: { status: 200, body: MEMBROS_DA_S1 },
      [invitesRoute("s1")]: { status: 200, body: [] },
      [createInviteRoute("s1")]: { status, body: corpo },
    });
    renderApp("/grupos/s1");
    fireEvent.click(await screen.findByRole("button", { name: "Gerar convite" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(mensagem);
    expect(alerta).not.toHaveTextContent("Traceback");
  });

  // --- o código é um segredo ---------------------------------------------------------------------

  it("nenhum cache de queries guarda o código do convite", async () => {
    const { client } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    const tudo = JSON.stringify(client.getQueryCache().getAll().map((q) => q.state.data));
    expect(tudo).not.toContain(CODIGO_DO_CONVITE);
  });

  it("Fechar apaga o código da tela", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));

    expect(screen.queryByRole("region", { name: "Novo convite" })).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(CODIGO_DO_CONVITE);
  });

  it("sair da página e voltar não traz o código de volta", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    fireEvent.click(screen.getByRole("link", { name: "Grupos" }));
    // (o link "Amigos" do cabeçalho é outro: procura-se o do grupo, dentro da lista de grupos)
    fireEvent.click(
      await within(await screen.findByRole("region", { name: "Seus grupos" })).findByRole("link", {
        name: "Amigos",
      }),
    );

    await screen.findByRole("region", { name: "Convites" });
    expect(screen.queryByRole("region", { name: "Novo convite" })).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(CODIGO_DO_CONVITE);
  });

  it("Copiar código copia o código e avisa", async () => {
    const escrever = vi.fn().mockResolvedValue(undefined);
    simularAreaDeTransferencia(escrever);
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    fireEvent.click(screen.getByRole("button", { name: "Copiar código" }));

    expect(await screen.findByText("Código copiado.")).toBeInTheDocument();
    expect(escrever).toHaveBeenCalledWith(CODIGO_DO_CONVITE);
  });

  it("sem área de transferência avisa para copiar à mão", async () => {
    await abrir(); // o jsdom não define `navigator.clipboard`: é o caso de um contexto não seguro
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    fireEvent.click(screen.getByRole("button", { name: "Copiar código" }));

    expect(
      await screen.findByText("Não foi possível copiar. Selecione o código e copie à mão."),
    ).toBeInTheDocument();
  });

  it("se a área de transferência recusar, também avisa para copiar à mão", async () => {
    simularAreaDeTransferencia(() => Promise.reject(new Error("negado")));
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Gerar convite" }));
    await screen.findByRole("region", { name: "Novo convite" });

    fireEvent.click(screen.getByRole("button", { name: "Copiar código" }));

    expect(
      await screen.findByText("Não foi possível copiar. Selecione o código e copie à mão."),
    ).toBeInTheDocument();
  });

  // --- revogar -----------------------------------------------------------------------------------

  it("Revogar pede confirmação: o 1º clique não faz DELETE, o segundo faz e o convite vira Revogado", async () => {
    const { m } = await abrir();
    await within(secao("Convites")).findByText("Ativo");

    fireEvent.click(screen.getByRole("button", { name: "Revogar convite 1" }));
    expect(m.callsTo(revokeInviteRoute("s1", "i1"))).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar Revogar convite 1" }));

    await waitFor(() => expect(within(secao("Convites")).queryByText("Ativo")).not.toBeInTheDocument());
    expect(within(secao("Convites")).getAllByText("Revogado")).toHaveLength(2);
    expect(m.callsTo(revokeInviteRoute("s1", "i1"))).toHaveLength(1);
    expect(m.callsTo(revokeInviteRoute("s1", "i1"))[0]!.headers["X-CSRFToken"]).toBe("tok");
    expect(screen.queryByRole("button", { name: /^Revogar convite/ })).not.toBeInTheDocument();
  });

  it("cancelar a revogação não faz nada", async () => {
    const { m } = await abrir();
    await within(secao("Convites")).findByText("Ativo");

    fireEvent.click(screen.getByRole("button", { name: "Revogar convite 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar Revogar convite 1" }));

    expect(m.callsTo(revokeInviteRoute("s1", "i1"))).toHaveLength(0);
    expect(within(secao("Convites")).getByText("Ativo")).toBeInTheDocument();
  });

  it("404 ao revogar (já não existe) avisa que mudou e recarrega a lista", async () => {
    const m = mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [roomRoute("s1")]: { status: 200, body: SALA_DONO },
      [membersRoute("s1")]: { status: 200, body: MEMBROS_DA_S1 },
      [invitesRoute("s1")]: { status: 200, body: [CONVITE_ATIVO] },
      [revokeInviteRoute("s1", "i1")]: { status: 404 },
    });
    renderApp("/grupos/s1");
    fireEvent.click(await screen.findByRole("button", { name: "Revogar convite 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar Revogar convite 1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Isso mudou. Atualizamos a lista.");
    await waitFor(() => expect(m.callsTo(invitesRoute("s1")).length).toBeGreaterThanOrEqual(2));
  });

  // --- cache -------------------------------------------------------------------------------------

  it("ao sair, os convites de quem saiu são removidos do cache", async () => {
    const { client } = await abrir();
    await within(secao("Convites")).findByText("Ativo");
    expect(client.getQueryData(invitesKey("s1"))).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await screen.findByRole("heading", { name: "Entrar" });
    expect(client.getQueryData(invitesKey("s1"))).toBeUndefined();
  });
});
