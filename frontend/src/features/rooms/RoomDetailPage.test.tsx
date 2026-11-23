import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  invitesRoute,
  MEMBROS_DA_S1,
  ROOMS,
  SALA_ADMIN,
  SALA_DONO,
  SALA_MEMBRO,
  SESSION,
  SESSION_AUTENTICADA,
  leaveRoute,
  membersRoute,
  renameRoute,
  roomRoute,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

const secao = (nome: string) => screen.getByRole("region", { name: nome });

/** Servidor simulado de UMA sala (`sala`), com os membros dados; renomear muda o estado. */
function simular(sala: typeof SALA_DONO, membros: unknown[] = MEMBROS_DA_S1) {
  let atual = sala;
  let saiu = false;
  return mockFetch({
    [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
    [ROOMS]: () => ({ status: 200, body: saiu ? [] : [atual] }),
    [roomRoute(sala.id)]: () => (saiu ? { status: 404 } : { status: 200, body: atual }),
    [membersRoute(sala.id)]: { status: 200, body: membros },
    // Dono e administrador também carregam os convites (a seção da 2.5c2); aqui, nenhum.
    [invitesRoute(sala.id)]: { status: 200, body: [] },
    [renameRoute(sala.id)]: (call) => {
      atual = { ...atual, name: (call.body as { name: string }).name };
      return { status: 200, body: atual };
    },
    [leaveRoute(sala.id)]: () => {
      saiu = true;
      return { status: 204 };
    },
  });
}

describe("RoomDetailPage", () => {
  it("sem sessão, /grupos/s1 redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: { status: 401 } } });

    renderApp("/grupos/s1");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });

  it("o dono vê nome, papel, quantos membros há de quantos cabem e cada membro com seu papel", async () => {
    simular(SALA_DONO);

    renderApp("/grupos/s1");

    expect(await screen.findByRole("heading", { name: "Amigos" })).toBeInTheDocument();
    expect(await screen.findByText("Seu papel: Dono")).toBeInTheDocument();
    const membros = within(secao("Membros"));
    expect(await membros.findByText("ana_01")).toBeInTheDocument();
    expect(membros.getByText("bruno_02")).toBeInTheDocument();
    expect(membros.getByText("Dono")).toBeInTheDocument();
    expect(membros.getByText("Membro")).toBeInTheDocument();
    expect(screen.getByText("2 de 20 membros")).toBeInTheDocument();
  });

  it("o dono pode renomear, não vê o botão Sair e é avisado de que não pode sair", async () => {
    simular(SALA_DONO);

    renderApp("/grupos/s1");

    await screen.findByRole("heading", { name: "Amigos" });
    expect(await screen.findByRole("region", { name: "Renomear grupo" })).toBeInTheDocument();
    // (o botão "Sair" do cabeçalho é o logout; aqui se procura o de sair DO GRUPO)
    expect(screen.queryByRole("button", { name: "Sair Amigos" })).not.toBeInTheDocument();
    expect(screen.getByText("O dono não pode sair do grupo.")).toBeInTheDocument();
  });

  it("o membro comum não vê o formulário de renomear, mas vê o botão Sair", async () => {
    simular(SALA_MEMBRO);

    renderApp("/grupos/s2");

    await screen.findByRole("heading", { name: "Time B" });
    expect(await screen.findByText("Seu papel: Membro")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Renomear grupo" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sair Time B" })).toBeInTheDocument();
    expect(screen.queryByText("O dono não pode sair do grupo.")).not.toBeInTheDocument();
  });

  it("o administrador pode renomear e também pode sair", async () => {
    simular(SALA_ADMIN);

    renderApp("/grupos/s3");

    await screen.findByRole("heading", { name: "Clube" });
    expect(await screen.findByRole("region", { name: "Renomear grupo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sair Clube" })).toBeInTheDocument();
  });

  // --- renomear --------------------------------------------------------------------------------

  it("Renomear vem com o nome atual e fica desabilitado enquanto o nome não muda ou está vazio", async () => {
    simular(SALA_DONO);
    renderApp("/grupos/s1");
    const campo = await screen.findByLabelText("Nome do grupo");
    const botao = screen.getByRole("button", { name: "Renomear" });

    expect(campo).toHaveValue("Amigos");
    expect(botao).toBeDisabled();
    fireEvent.change(campo, { target: { value: "   " } });
    expect(botao).toBeDisabled();
    fireEvent.change(campo, { target: { value: "Amigos CS" } });
    expect(botao).toBeEnabled();
  });

  it("renomear faz PATCH com CSRF e o novo nome aparece no título", async () => {
    const m = simular(SALA_DONO);
    renderApp("/grupos/s1");
    fireEvent.change(await screen.findByLabelText("Nome do grupo"), {
      target: { value: "  Amigos CS " },
    });

    fireEvent.click(screen.getByRole("button", { name: "Renomear" }));

    expect(await screen.findByRole("heading", { name: "Amigos CS" })).toBeInTheDocument();
    expect(m.callsTo(renameRoute("s1"))).toHaveLength(1);
    expect(m.callsTo(renameRoute("s1"))[0]!.body).toEqual({ name: "Amigos CS" });
    expect(m.callsTo(renameRoute("s1"))[0]!.headers["X-CSRFToken"]).toBe("tok");
  });

  it("erro ao renomear mostra a mensagem própria, nunca o texto do servidor", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [roomRoute("s1")]: { status: 200, body: SALA_DONO },
      [membersRoute("s1")]: { status: 200, body: MEMBROS_DA_S1 },
      [invitesRoute("s1")]: { status: 200, body: [] },
      [renameRoute("s1")]: { status: 400, body: { name: ["Ensure this field has no more than 60 characters."] } },
    });
    renderApp("/grupos/s1");
    fireEvent.change(await screen.findByLabelText("Nome do grupo"), { target: { value: "Outro" } });

    fireEvent.click(screen.getByRole("button", { name: "Renomear" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Informe um nome de 1 a 60 caracteres.");
    expect(alerta).not.toHaveTextContent("Ensure");
  });

  // --- sair ------------------------------------------------------------------------------------

  it("Sair pede confirmação: o 1º clique não faz POST, o segundo faz e volta para /grupos", async () => {
    const m = simular(SALA_MEMBRO);
    renderApp("/grupos/s2");

    fireEvent.click(await screen.findByRole("button", { name: "Sair Time B" }));
    expect(m.callsTo(leaveRoute("s2"))).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar Sair Time B" }));

    expect(await screen.findByRole("heading", { name: "Grupos" })).toBeInTheDocument();
    expect(m.callsTo(leaveRoute("s2"))).toHaveLength(1);
    expect(m.callsTo(leaveRoute("s2"))[0]!.headers["X-CSRFToken"]).toBe("tok");
    expect(await screen.findByText("Você ainda não está em nenhum grupo.")).toBeInTheDocument();
  });

  it("cancelar a saída não faz nada", async () => {
    const m = simular(SALA_MEMBRO);
    renderApp("/grupos/s2");

    fireEvent.click(await screen.findByRole("button", { name: "Sair Time B" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar Sair Time B" }));

    expect(m.callsTo(leaveRoute("s2"))).toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Time B" })).toBeInTheDocument();
  });

  it("404 ao sair (já tinha saído em outra aba) também volta para /grupos", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [ROOMS]: { status: 200, body: [] },
      [roomRoute("s2")]: { status: 200, body: SALA_MEMBRO },
      [membersRoute("s2")]: { status: 200, body: MEMBROS_DA_S1 },
      [leaveRoute("s2")]: { status: 404 },
    });
    renderApp("/grupos/s2");

    fireEvent.click(await screen.findByRole("button", { name: "Sair Time B" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar Sair Time B" }));

    expect(await screen.findByRole("heading", { name: "Grupos" })).toBeInTheDocument();
  });

  // --- erros de carga ----------------------------------------------------------------------------

  it("grupo que não existe (ou de que a pessoa saiu) mostra 'Grupo não encontrado.' e um caminho de volta", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [roomRoute("s7")]: { status: 404 },
      [membersRoute("s7")]: { status: 404 },
    });

    renderApp("/grupos/s7");

    expect(await screen.findByText("Grupo não encontrado.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voltar aos grupos" })).toHaveAttribute("href", "/grupos");
  });

  it("falha ao carregar só os membros avisa, e o nome do grupo continua na tela", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [roomRoute("s1")]: { status: 200, body: SALA_DONO },
      [membersRoute("s1")]: { status: 500 },
      [invitesRoute("s1")]: { status: 200, body: [] },
    });

    renderApp("/grupos/s1");

    expect(await screen.findByRole("heading", { name: "Amigos" })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Não foi possível carregar os membros. Tente novamente.",
      ),
    );
  });
});
