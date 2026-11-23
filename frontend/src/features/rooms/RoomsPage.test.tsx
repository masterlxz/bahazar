import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  CREATE_ROOM,
  ERRO_CONVITE,
  ERRO_LIMITE_DE_SALAS,
  JOIN_ROOM,
  LOGOUT,
  MEMBROS_DA_S1,
  ROOMS,
  invitesRoute,
  SALA_DONO,
  SALA_MEMBRO,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  membersRoute,
  roomRoute,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";
import { ROOMS_LIST_KEY } from "./useRooms";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

const NOVA = { ...SALA_DONO, id: "s9", name: "Novo" };

/** Servidor simulado: as salas e os detalhes que o app pode pedir. */
function simular(opcoes: { esperaDaCriacao?: Promise<unknown> } = {}) {
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
    [ROOMS]: { status: 200, body: [SALA_DONO, SALA_MEMBRO] },
    [CREATE_ROOM]: { status: 201, body: NOVA, wait: opcoes.esperaDaCriacao },
    [JOIN_ROOM]: { status: 200, body: SALA_MEMBRO },
    [roomRoute("s9")]: { status: 200, body: NOVA },
    [membersRoute("s9")]: { status: 200, body: [MEMBROS_DA_S1[0]] },
    [invitesRoute("s9")]: { status: 200, body: [] }, // quem cria é dono: a seção carrega convites
    [roomRoute("s2")]: { status: 200, body: SALA_MEMBRO },
    [membersRoute("s2")]: { status: 200, body: MEMBROS_DA_S1 },
  });
}

async function abrir() {
  const m = simular();
  const app = renderApp("/grupos");
  await screen.findByRole("heading", { name: "Grupos" });
  await within(secao("Seus grupos")).findByText("Amigos");
  return { m, ...app };
}

const secao = (nome: string) => screen.getByRole("region", { name: nome });

describe("RoomsPage", () => {
  it("sem sessão, /grupos redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/grupos");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Grupos" })).not.toBeInTheDocument();
  });

  it("lista os grupos com o papel de quem pergunta e um link para o detalhe", async () => {
    await abrir();

    const lista = within(secao("Seus grupos"));
    expect(lista.getByRole("link", { name: "Amigos" })).toHaveAttribute("href", "/grupos/s1");
    expect(lista.getByRole("link", { name: "Time B" })).toHaveAttribute("href", "/grupos/s2");
    expect(lista.getByText("Dono")).toBeInTheDocument();
    expect(lista.getByText("Membro")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Grupos" })).toBeInTheDocument();
  });

  it("sem grupos mostra uma mensagem em vez de ficar em branco", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [ROOMS]: { status: 200, body: [] },
    });

    renderApp("/grupos");

    expect(await screen.findByText("Você ainda não está em nenhum grupo.")).toBeInTheDocument();
  });

  it("falha ao carregar os grupos mostra um aviso", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [ROOMS]: { status: 500 },
    });

    renderApp("/grupos");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar seus grupos. Tente novamente.",
    );
  });

  // --- criar ---------------------------------------------------------------------------------

  it("Criar grupo fica desabilitado com o nome vazio ou só com espaços", async () => {
    await abrir();
    const botao = screen.getByRole("button", { name: "Criar grupo" });
    expect(botao).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Nome do grupo"), { target: { value: "   " } });

    expect(botao).toBeDisabled();
  });

  it("cria o grupo (nome sem espaços nas pontas, com CSRF) e leva ao detalhe dele", async () => {
    const { m } = await abrir();
    fireEvent.change(screen.getByLabelText("Nome do grupo"), { target: { value: "  Novo " } });

    fireEvent.click(screen.getByRole("button", { name: "Criar grupo" }));

    expect(await screen.findByRole("heading", { name: "Novo" })).toBeInTheDocument();
    expect(m.callsTo(CREATE_ROOM)).toHaveLength(1);
    expect(m.callsTo(CREATE_ROOM)[0]!.body).toEqual({ name: "Novo" });
    expect(m.callsTo(CREATE_ROOM)[0]!.headers["X-CSRFToken"]).toBe("tok");
  });

  it("enquanto a criação está pendente o botão fica desabilitado e o clique extra não envia outro POST", async () => {
    let liberar: () => void = () => {};
    const espera = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    const m = simular({ esperaDaCriacao: espera });
    renderApp("/grupos");
    fireEvent.change(await screen.findByLabelText("Nome do grupo"), { target: { value: "Novo" } });
    const botao = screen.getByRole("button", { name: "Criar grupo" });

    fireEvent.click(botao);
    await waitFor(() => expect(screen.getByRole("button", { name: "Criar grupo" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Criar grupo" }));
    fireEvent.click(screen.getByRole("button", { name: "Criar grupo" }));

    liberar();
    await screen.findByRole("heading", { name: "Novo" });
    expect(m.callsTo(CREATE_ROOM)).toHaveLength(1);
  });

  it.each([
    [409, ERRO_LIMITE_DE_SALAS, "Você já é dono de 5 grupos."],
    [400, { name: ["Este campo não pode ser em branco."] }, "Informe um nome de 1 a 60 caracteres."],
    [500, { code: "boom", message: "Traceback (most recent call last)" }, "Não foi possível criar o grupo. Tente novamente."],
  ])("erro %i ao criar mostra a mensagem própria, nunca o texto do servidor", async (status, corpo, mensagem) => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [ROOMS]: { status: 200, body: [] },
      [CREATE_ROOM]: { status, body: corpo },
    });
    renderApp("/grupos");
    fireEvent.change(await screen.findByLabelText("Nome do grupo"), { target: { value: "Novo" } });

    fireEvent.click(screen.getByRole("button", { name: "Criar grupo" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(mensagem);
    expect(alerta).not.toHaveTextContent("Traceback");
  });

  // --- entrar por código -----------------------------------------------------------------------

  it("Entrar no grupo fica desabilitado com o código vazio", async () => {
    await abrir();

    expect(screen.getByRole("button", { name: "Entrar no grupo" })).toBeDisabled();
  });

  it("entra com o código no CORPO do POST (nunca na URL) e leva ao detalhe", async () => {
    const { m } = await abrir();
    fireEvent.change(screen.getByLabelText("Código do convite"), { target: { value: " segredo123 " } });

    fireEvent.click(screen.getByRole("button", { name: "Entrar no grupo" }));

    expect(await screen.findByRole("heading", { name: "Time B" })).toBeInTheDocument();
    const chamada = m.callsTo(JOIN_ROOM)[0]!;
    expect(chamada.body).toEqual({ code: "segredo123" });
    expect(chamada.url).toBe("/api/v1/rooms/join/");
    expect(chamada.headers["X-CSRFToken"]).toBe("tok");
    expect(m.calls.some((c) => c.url.includes("segredo123"))).toBe(false);
  });

  it.each([
    [404, undefined, "Convite não encontrado."],
    [409, ERRO_CONVITE.invite_expired, "Este convite expirou."],
    [409, ERRO_CONVITE.invite_revoked, "Este convite foi revogado."],
    [409, ERRO_CONVITE.invite_exhausted, "Este convite já foi usado o máximo de vezes."],
    [409, ERRO_CONVITE.room_full, "A sala está cheia."],
    [409, ERRO_CONVITE.room_archived, "A sala foi arquivada."],
    [429, undefined, "Muitas tentativas. Espere um minuto e tente de novo."],
    [400, { code: ["Informe o código do convite."] }, "Informe o código do convite."],
    [500, { code: "boom", message: "Traceback (most recent call last)" }, "Não foi possível entrar no grupo. Tente novamente."],
  ])("erro %i ao entrar (%o) mostra a mensagem do caso, sem eco do código nem do servidor", async (status, corpo, mensagem) => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [ROOMS]: { status: 200, body: [] },
      [JOIN_ROOM]: { status, body: corpo },
    });
    renderApp("/grupos");
    fireEvent.change(await screen.findByLabelText("Código do convite"), { target: { value: "segredo123" } });

    fireEvent.click(screen.getByRole("button", { name: "Entrar no grupo" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(mensagem);
    expect(alerta).not.toHaveTextContent("segredo123");
    expect(alerta).not.toHaveTextContent("Traceback");
  });

  // --- cache -----------------------------------------------------------------------------------

  it("ao sair, a lista de grupos de quem saiu é removida do cache", async () => {
    const { client } = await abrir();
    expect(client.getQueryData(ROOMS_LIST_KEY)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await screen.findByRole("heading", { name: "Entrar" });
    expect(client.getQueryData(ROOMS_LIST_KEY)).toBeUndefined();
  });
});
