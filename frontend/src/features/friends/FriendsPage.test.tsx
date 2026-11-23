import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import {
  BLOCKS,
  CARLA,
  ERRO_JA_AMIGOS,
  ERRO_JA_PENDENTE,
  ERRO_PEDIDO_INDISPONIVEL,
  EVA,
  FRIENDS,
  LOGOUT,
  PEDIDO_DO_BRUNO,
  PEDIDO_PARA_DIEGO,
  REQUESTS,
  SEND_REQUEST,
  SENT,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  acceptRoute,
  blockRoute,
  declineRoute,
  removeRoute,
  unblockRoute,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";
import { FRIENDS_LIST_KEY } from "./useFriends";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

/** Servidor simulado com estado: cada ação muda as listas que as próximas leituras devolvem. */
function simular(opcoes: { esperaDoAceite?: Promise<unknown> } = {}) {
  let amigos: unknown[] = [CARLA];
  let recebidos: unknown[] = [PEDIDO_DO_BRUNO];
  let enviados: unknown[] = [PEDIDO_PARA_DIEGO];
  let bloqueados: unknown[] = [EVA];
  let logado = true;
  const m = mockFetch({
    [SESSION]: () =>
      logado
        ? { status: 200, body: SESSION_AUTENTICADA }
        : { status: 401, body: SESSION_ANONIMA },
    [LOGOUT]: () => {
      logado = false;
      return { status: 401, body: SESSION_ANONIMA };
    },
    [FRIENDS]: () => ({ status: 200, body: amigos }),
    [REQUESTS]: () => ({ status: 200, body: recebidos }),
    [SENT]: () => ({ status: 200, body: enviados }),
    [BLOCKS]: () => ({ status: 200, body: bloqueados }),
    [SEND_REQUEST]: (call) => {
      const username = (call.body as { username: string }).username;
      const novo = { ...PEDIDO_PARA_DIEGO, id: "r9", addressee: username };
      enviados = [...enviados, novo];
      return { status: 201, body: novo };
    },
    [acceptRoute("r1")]: () => {
      amigos = [...amigos, { username: "bruno_02", avatar: "default" }];
      recebidos = [];
      return { status: 200, body: { ...PEDIDO_DO_BRUNO, status: "accepted" }, wait: opcoes.esperaDoAceite };
    },
    [declineRoute("r1")]: () => {
      recebidos = [];
      return { status: 204 };
    },
    [removeRoute("carla_03")]: () => {
      amigos = amigos.filter((a) => (a as { username: string }).username !== "carla_03");
      return { status: 204 };
    },
    [blockRoute("carla_03")]: () => {
      amigos = amigos.filter((a) => (a as { username: string }).username !== "carla_03");
      bloqueados = [...bloqueados, CARLA];
      return { status: 204 };
    },
    [unblockRoute("eva_05")]: () => {
      bloqueados = [];
      return { status: 204 };
    },
  });
  return m;
}

const secao = (nome: string) => screen.getByRole("region", { name: nome });

async function abrir() {
  const m = simular();
  const app = renderApp("/amigos");
  await screen.findByRole("heading", { name: "Amigos" });
  await within(secao("Seus amigos")).findByText("carla_03");
  return { m, ...app };
}

describe("FriendsPage", () => {
  it("sem sessão, /amigos redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/amigos");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Amigos" })).not.toBeInTheDocument();
  });

  it("mostra amigos, pedidos recebidos e enviados e bloqueados, cada um na sua seção", async () => {
    await abrir();

    expect(within(secao("Seus amigos")).getByText("carla_03")).toBeInTheDocument();
    expect(within(secao("Pedidos recebidos")).getByText("bruno_02")).toBeInTheDocument();
    expect(within(secao("Pedidos enviados")).getByText("diego_04")).toBeInTheDocument();
    expect(within(secao("Bloqueados")).getByText("eva_05")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Amigos" })).toBeInTheDocument();
  });

  it("listas vazias mostram uma mensagem em vez de ficar em branco", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [FRIENDS]: { status: 200, body: [] },
      [REQUESTS]: { status: 200, body: [] },
      [SENT]: { status: 200, body: [] },
      [BLOCKS]: { status: 200, body: [] },
    });

    renderApp("/amigos");

    expect(await screen.findByText("Você ainda não tem amigos.")).toBeInTheDocument();
    expect(screen.getByText("Nenhum pedido recebido.")).toBeInTheDocument();
    expect(screen.getByText("Nenhum pedido enviado.")).toBeInTheDocument();
    expect(screen.getByText("Você não bloqueou ninguém.")).toBeInTheDocument();
  });

  it("falha ao carregar uma lista mostra um aviso", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [FRIENDS]: { status: 500 },
      [REQUESTS]: { status: 200, body: [] },
      [SENT]: { status: 200, body: [] },
      [BLOCKS]: { status: 200, body: [] },
    });

    renderApp("/amigos");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar suas listas de amigos. Tente novamente.",
    );
  });

  // --- enviar pedido ---------------------------------------------------------------------

  it("Enviar pedido fica desabilitado com o campo vazio ou só com espaços", async () => {
    await abrir();
    const botao = screen.getByRole("button", { name: "Enviar pedido" });
    expect(botao).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Nome de usuário"), { target: { value: "   " } });

    expect(botao).toBeDisabled();
  });

  it("envia o pedido (sem espaços nas pontas, com CSRF), limpa o campo e lista em Enviados", async () => {
    const { m } = await abrir();
    const campo = screen.getByLabelText("Nome de usuário");
    fireEvent.change(campo, { target: { value: "  frida_06 " } });

    fireEvent.click(screen.getByRole("button", { name: "Enviar pedido" }));

    expect(await within(secao("Pedidos enviados")).findByText("frida_06")).toBeInTheDocument();
    expect(m.callsTo(SEND_REQUEST)).toHaveLength(1);
    expect(m.callsTo(SEND_REQUEST)[0]!.body).toEqual({ username: "frida_06" });
    expect(m.callsTo(SEND_REQUEST)[0]!.headers["X-CSRFToken"]).toBe("tok");
    expect(campo).toHaveValue("");
  });

  it.each([
    [ERRO_PEDIDO_INDISPONIVEL, "Não foi possível enviar o pedido a este jogador."],
    [ERRO_JA_PENDENTE, "Já existe um pedido pendente entre vocês."],
    [ERRO_JA_AMIGOS, "Vocês já são amigos."],
  ])("409 %o mostra a mensagem do código", async (erro, mensagem) => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [FRIENDS]: { status: 200, body: [] },
      [REQUESTS]: { status: 200, body: [] },
      [SENT]: { status: 200, body: [] },
      [BLOCKS]: { status: 200, body: [] },
      [SEND_REQUEST]: { status: 409, body: erro },
    });
    renderApp("/amigos");
    fireEvent.change(await screen.findByLabelText("Nome de usuário"), {
      target: { value: "alguem_07" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Enviar pedido" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(mensagem);
  });

  it("erro inesperado ao enviar mostra mensagem própria, nunca o texto do servidor", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [FRIENDS]: { status: 200, body: [] },
      [REQUESTS]: { status: 200, body: [] },
      [SENT]: { status: 200, body: [] },
      [BLOCKS]: { status: 200, body: [] },
      [SEND_REQUEST]: { status: 500, body: { code: "boom", message: "Traceback (most recent call last)" } },
    });
    renderApp("/amigos");
    fireEvent.change(await screen.findByLabelText("Nome de usuário"), {
      target: { value: "alguem_07" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Enviar pedido" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Não foi possível enviar o pedido. Tente novamente.");
    expect(alerta).not.toHaveTextContent("Traceback");
  });

  // --- aceitar e recusar -----------------------------------------------------------------

  it("Aceitar faz POST com CSRF e o pedido vira amigo, saindo de Recebidos", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Aceitar bruno_02" }));

    expect(await within(secao("Seus amigos")).findByText("bruno_02")).toBeInTheDocument();
    expect(m.callsTo(acceptRoute("r1"))).toHaveLength(1);
    expect(m.callsTo(acceptRoute("r1"))[0]!.headers["X-CSRFToken"]).toBe("tok");
    expect(within(secao("Pedidos recebidos")).queryByText("bruno_02")).not.toBeInTheDocument();
  });

  it("Recusar tira o pedido de Recebidos e não cria amizade", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Recusar bruno_02" }));

    await waitFor(() =>
      expect(within(secao("Pedidos recebidos")).queryByText("bruno_02")).not.toBeInTheDocument(),
    );
    expect(m.callsTo(declineRoute("r1"))).toHaveLength(1);
    expect(within(secao("Seus amigos")).queryByText("bruno_02")).not.toBeInTheDocument();
  });

  it("enquanto o aceite está pendente os botões ficam desabilitados e o clique extra não envia outro POST", async () => {
    let liberar: () => void = () => {};
    const espera = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    const m = simular({ esperaDoAceite: espera });
    renderApp("/amigos");
    const aceitar = await screen.findByRole("button", { name: "Aceitar bruno_02" });

    fireEvent.click(aceitar);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aceitar bruno_02" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Recusar bruno_02" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Aceitar bruno_02" }));
    fireEvent.click(screen.getByRole("button", { name: "Aceitar bruno_02" }));

    liberar();
    await within(secao("Seus amigos")).findByText("bruno_02");
    expect(m.callsTo(acceptRoute("r1"))).toHaveLength(1);
  });

  it("404 ao aceitar (o pedido já não existe) avisa que mudou e recarrega as listas", async () => {
    let pedidoExiste = true;
    const m = mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [FRIENDS]: { status: 200, body: [] },
      [REQUESTS]: () => ({ status: 200, body: pedidoExiste ? [PEDIDO_DO_BRUNO] : [] }),
      [SENT]: { status: 200, body: [] },
      [BLOCKS]: { status: 200, body: [] },
      [acceptRoute("r1")]: () => {
        pedidoExiste = false;
        return { status: 404 };
      },
    });
    renderApp("/amigos");
    fireEvent.click(await screen.findByRole("button", { name: "Aceitar bruno_02" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Isso mudou. Atualizamos a lista.");
    await waitFor(() => expect(m.callsTo(REQUESTS).length).toBeGreaterThanOrEqual(2));
    expect(within(secao("Pedidos recebidos")).queryByText("bruno_02")).not.toBeInTheDocument();
  });

  // --- remover e bloquear (com confirmação) ----------------------------------------------

  it("Remover pede confirmação: o 1º clique não faz DELETE, o segundo faz", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Remover carla_03" }));
    expect(m.callsTo(removeRoute("carla_03"))).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar Remover carla_03" }));

    await waitFor(() =>
      expect(within(secao("Seus amigos")).queryByText("carla_03")).not.toBeInTheDocument(),
    );
    expect(m.callsTo(removeRoute("carla_03"))).toHaveLength(1);
    expect(m.callsTo(removeRoute("carla_03"))[0]!.headers["X-CSRFToken"]).toBe("tok");
  });

  it("cancelar a remoção não faz nada e mantém o amigo", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Remover carla_03" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar Remover carla_03" }));

    expect(m.callsTo(removeRoute("carla_03"))).toHaveLength(0);
    expect(within(secao("Seus amigos")).getByText("carla_03")).toBeInTheDocument();
  });

  it("Bloquear (confirmado) tira o amigo de Amigos e o põe em Bloqueados", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Bloquear carla_03" }));
    expect(m.callsTo(blockRoute("carla_03"))).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar Bloquear carla_03" }));

    await waitFor(() =>
      expect(within(secao("Seus amigos")).queryByText("carla_03")).not.toBeInTheDocument(),
    );
    expect(await within(secao("Bloqueados")).findByText("carla_03")).toBeInTheDocument();
    expect(m.callsTo(blockRoute("carla_03"))).toHaveLength(1);
  });

  it("Desbloquear tira da lista de Bloqueados (sem confirmação: é reversível)", async () => {
    const { m } = await abrir();

    fireEvent.click(screen.getByRole("button", { name: "Desbloquear eva_05" }));

    await waitFor(() =>
      expect(within(secao("Bloqueados")).queryByText("eva_05")).not.toBeInTheDocument(),
    );
    expect(m.callsTo(unblockRoute("eva_05"))).toHaveLength(1);
    expect(m.callsTo(unblockRoute("eva_05"))[0]!.headers["X-CSRFToken"]).toBe("tok");
  });

  // --- cache -----------------------------------------------------------------------------

  it("ao sair, as listas de quem saiu são removidas do cache", async () => {
    const { client } = await abrir();
    expect(client.getQueryData(FRIENDS_LIST_KEY)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await screen.findByRole("heading", { name: "Entrar" });
    expect(client.getQueryData(FRIENDS_LIST_KEY)).toBeUndefined();
  });
});
