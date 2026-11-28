import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch, type MockHandler } from "../../test/fetchMock";
import {
  ITEM_AK,
  ITEM_AWP,
  LOGOUT,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  pagina,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";
import { INVENTORY_ROOT_KEY } from "../inventory/useInventory";
import { TRADES_ROOT_KEY } from "./useTrades";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

// --- Fixtures: formato de `TradeOfferSerializer` (apps/trades/serializers.py, lido em 2026-11-28).
// `side` é "offered" (quem propõe dá) ou "requested" (quem propõe pede). O usuário da sessão é ana_01.

const doItem = (item: typeof ITEM_AK, side: "offered" | "requested") => ({
  side,
  id: item.id,
  skin: item.skin,
  float_value: item.float_value,
  wear: item.wear,
  reference_price: item.reference_price,
});

const BRUNO = { username: "bruno_02", avatar: "default" };
const CARLA = { username: "carla_03", avatar: "default" };
const ANA = { username: "ana_01", avatar: "default" };

/** Bruno oferece a AK-47 Redline (US$ 25,75) e pede a AWP Asiimov (US$ 19,99) da ana. */
const OFERTA_DO_BRUNO = {
  id: "o1",
  status: "pending",
  created_at: "2026-11-27T12:00:00Z",
  resolved_at: null as string | null,
  proposer: BRUNO,
  recipient: ANA,
  items: [doItem(ITEM_AK, "offered"), doItem(ITEM_AWP, "requested")],
};
/** A ana propôs ao bruno: aqui ela é a proponente. */
const OFERTA_DA_ANA = {
  ...OFERTA_DO_BRUNO,
  id: "o3",
  proposer: ANA,
  recipient: BRUNO,
  items: [doItem(ITEM_AWP, "offered"), doItem(ITEM_AK, "requested")],
};
/** Carla propôs à ana (segunda oferta pendente, para provar que um clique trava os outros botões). */
const OFERTA_DA_CARLA = { ...OFERTA_DO_BRUNO, id: "o2", proposer: CARLA };

const TRADES = (page = 1) => `GET /api/v1/trades/?page=${page}`;
const ACAO = (id: string, acao: "accept" | "decline" | "cancel") =>
  `POST /api/v1/trades/${id}/${acao}/`;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Oferta = typeof OFERTA_DO_BRUNO;

/** Servidor simulado com estado: resolver uma oferta muda o que a próxima leitura da lista devolve. */
function simular(ofertas: Oferta[], extras: Record<string, MockHandler> = {}) {
  let lista = ofertas;
  const resolver = (id: string, status: string) => {
    lista = lista.map((o) =>
      o.id === id ? { ...o, status, resolved_at: "2026-11-28T12:00:00Z" } : o,
    );
    return lista.find((o) => o.id === id);
  };
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
    [TRADES(1)]: () => ({ status: 200, body: pagina(lista) }),
    [ACAO("o1", "accept")]: () => ({ status: 200, body: resolver("o1", "accepted") }),
    [ACAO("o1", "decline")]: () => ({ status: 200, body: resolver("o1", "declined") }),
    [ACAO("o2", "decline")]: () => ({ status: 200, body: resolver("o2", "declined") }),
    [ACAO("o3", "cancel")]: () => ({ status: 200, body: resolver("o3", "cancelled") }),
    ...extras,
  });
}

async function abrir(ofertas: Oferta[], extras: Record<string, MockHandler> = {}) {
  const m = simular(ofertas, extras);
  const app = renderApp("/trocas");
  await screen.findByRole("heading", { name: "Trocas" });
  return { m, ...app };
}

const oferta = (proposer: string, recipient: string) =>
  screen.getByRole("article", { name: `Oferta de ${proposer} para ${recipient}` });

const MUDOU = "Essa oferta mudou. Atualizamos a lista.";
const FALHOU = "Não foi possível concluir a ação. Tente novamente.";

describe("TradesPage", () => {
  it("sem sessão, /trocas redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/trocas");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Trocas" })).not.toBeInTheDocument();
  });

  it("o menu de quem está logado tem o link Trocas", async () => {
    await abrir([OFERTA_DO_BRUNO]);

    expect(screen.getByRole("link", { name: "Trocas" })).toHaveAttribute("href", "/trocas");
  });

  // --- leitura -------------------------------------------------------------------------------

  it("mostra a oferta com quem propôs, os itens de cada lado, o desgaste e o preço de referência", async () => {
    await abrir([OFERTA_DO_BRUNO]);
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    expect(within(card).getByText("Pendente")).toBeInTheDocument();
    const oferecido = within(card).getByRole("group", { name: "Oferecido" });
    expect(within(oferecido).getByText("Redline")).toBeInTheDocument();
    expect(within(oferecido).getByText("AK-47")).toBeInTheDocument();
    expect(within(oferecido).getByText("Field-Tested")).toBeInTheDocument();
    expect(within(oferecido).getByText("US$ 25,75")).toBeInTheDocument();
    const pedido = within(card).getByRole("group", { name: "Pedido" });
    expect(within(pedido).getByText("Asiimov")).toBeInTheDocument();
    expect(within(pedido).getByText("Well-Worn")).toBeInTheDocument();
    expect(within(pedido).getByText("US$ 19,99")).toBeInTheDocument();
  });

  it("a atribuição 'via Skinport' aparece uma vez na tela, não por oferta", async () => {
    await abrir([OFERTA_DO_BRUNO, OFERTA_DA_CARLA]);
    await screen.findByRole("article", { name: "Oferta de carla_03 para ana_01" });

    expect(screen.getAllByRole("link", { name: "Skinport" })).toHaveLength(1);
  });

  it("lista vazia mostra 'Nenhuma oferta.' e nenhuma atribuição", async () => {
    await abrir([]);

    expect(await screen.findByText("Nenhuma oferta.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Skinport" })).not.toBeInTheDocument();
  });

  it("falha ao carregar mostra um aviso", async () => {
    mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [TRADES(1)]: { status: 500 },
    });

    renderApp("/trocas");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar suas ofertas. Tente novamente.",
    );
  });

  it("duas páginas: 'Próxima' pede a página 2 e troca a lista; 'Anterior' começa desabilitado", async () => {
    const m = mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      [TRADES(1)]: {
        status: 200,
        body: pagina([OFERTA_DO_BRUNO], {
          count: 21,
          next: "http://localhost/api/v1/trades/?page=2",
        }),
      },
      [TRADES(2)]: {
        status: 200,
        body: pagina([OFERTA_DA_CARLA], {
          count: 21,
          previous: "http://localhost/api/v1/trades/",
        }),
      },
    });
    renderApp("/trocas");
    await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Próxima" }));

    expect(
      await screen.findByRole("article", { name: "Oferta de carla_03 para ana_01" }),
    ).toBeInTheDocument();
    expect(m.callsTo(TRADES(2))).toHaveLength(1);
    expect(screen.queryByRole("article", { name: "Oferta de bruno_02 para ana_01" })).toBeNull();
    expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
  });

  // --- quem pode fazer o quê ------------------------------------------------------------------

  it("destinatário de oferta pendente vê Aceitar e Recusar, e não Cancelar", async () => {
    await abrir([OFERTA_DO_BRUNO]);
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    expect(within(card).getByRole("button", { name: "Aceitar oferta de bruno_02" })).toBeEnabled();
    expect(within(card).getByRole("button", { name: "Recusar" })).toBeEnabled();
    expect(within(card).queryByRole("button", { name: "Cancelar oferta" })).toBeNull();
  });

  it("proponente de oferta pendente vê só Cancelar", async () => {
    await abrir([OFERTA_DA_ANA]);
    const card = await screen.findByRole("article", { name: "Oferta de ana_01 para bruno_02" });

    expect(within(card).getByRole("button", { name: "Cancelar oferta" })).toBeEnabled();
    expect(within(card).queryByRole("button", { name: /Aceitar/ })).toBeNull();
    expect(within(card).queryByRole("button", { name: "Recusar" })).toBeNull();
  });

  it.each([
    ["accepted", "Aceita"],
    ["declined", "Recusada"],
    ["cancelled", "Cancelada"],
    ["expired", "Expirada"],
  ])("oferta %s mostra '%s' e nenhum botão de ação, para quem recebeu e para quem propôs", async (status, rotulo) => {
    await abrir([
      { ...OFERTA_DO_BRUNO, status },
      { ...OFERTA_DA_ANA, status },
    ]);
    const recebida = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });
    const enviada = oferta("ana_01", "bruno_02");

    for (const card of [recebida, enviada]) {
      expect(within(card).getByText(rotulo)).toBeInTheDocument();
      expect(within(card).queryAllByRole("button")).toHaveLength(0);
    }
  });

  // --- ações ----------------------------------------------------------------------------------

  it("o 1º clique em Aceitar só pede confirmação: nada é enviado", async () => {
    const { m } = await abrir([OFERTA_DO_BRUNO]);
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    fireEvent.click(within(card).getByRole("button", { name: "Aceitar oferta de bruno_02" }));

    expect(
      within(card).getByRole("button", { name: "Confirmar Aceitar oferta de bruno_02" }),
    ).toBeInTheDocument();
    expect(m.callsTo(ACAO("o1", "accept"))).toHaveLength(0);
  });

  it("confirmar o aceite envia POST /accept/ com CSRF e Idempotency-Key (UUID), e a lista mostra 'Aceita'", async () => {
    const { m } = await abrir([OFERTA_DO_BRUNO]);
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    fireEvent.click(within(card).getByRole("button", { name: "Aceitar oferta de bruno_02" }));
    fireEvent.click(
      within(card).getByRole("button", { name: "Confirmar Aceitar oferta de bruno_02" }),
    );

    expect(await within(card).findByText("Aceita")).toBeInTheDocument();
    const chamadas = m.callsTo(ACAO("o1", "accept"));
    expect(chamadas).toHaveLength(1);
    expect(chamadas[0]!.headers["X-CSRFToken"]).toBe("tok");
    expect(chamadas[0]!.headers["Idempotency-Key"]).toMatch(UUID);
    expect(m.callsTo(ACAO("o1", "decline"))).toHaveLength(0);
    expect(m.callsTo(TRADES(1)).length).toBeGreaterThanOrEqual(2); // recarregou depois da ação
  });

  it("aceitar marca o inventário em cache como desatualizado (os donos mudaram)", async () => {
    const { client } = await abrir([OFERTA_DO_BRUNO]);
    const chaveDoInventario = [...INVENTORY_ROOT_KEY, "mine", {}] as const;
    client.setQueryData(chaveDoInventario, pagina([]));
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    fireEvent.click(within(card).getByRole("button", { name: "Aceitar oferta de bruno_02" }));
    fireEvent.click(
      within(card).getByRole("button", { name: "Confirmar Aceitar oferta de bruno_02" }),
    );

    await within(card).findByText("Aceita");
    expect(client.getQueryState(chaveDoInventario)?.isInvalidated).toBe(true);
  });

  it("recusar (sem confirmação) envia POST /decline/ e NÃO mexe no inventário", async () => {
    const { m, client } = await abrir([OFERTA_DO_BRUNO]);
    const chaveDoInventario = [...INVENTORY_ROOT_KEY, "mine", {}] as const;
    client.setQueryData(chaveDoInventario, pagina([]));
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    fireEvent.click(within(card).getByRole("button", { name: "Recusar" }));

    expect(await within(card).findByText("Recusada")).toBeInTheDocument();
    expect(m.callsTo(ACAO("o1", "decline"))).toHaveLength(1);
    expect(m.callsTo(ACAO("o1", "accept"))).toHaveLength(0);
    expect(client.getQueryState(chaveDoInventario)?.isInvalidated).toBe(false);
  });

  it("o proponente cancela com POST /cancel/", async () => {
    const { m } = await abrir([OFERTA_DA_ANA]);
    const card = await screen.findByRole("article", { name: "Oferta de ana_01 para bruno_02" });

    fireEvent.click(within(card).getByRole("button", { name: "Cancelar oferta" }));

    expect(await within(card).findByText("Cancelada")).toBeInTheDocument();
    expect(m.callsTo(ACAO("o3", "cancel"))).toHaveLength(1);
    expect(m.callsTo(ACAO("o3", "cancel"))[0]!.headers["Idempotency-Key"]).toMatch(UUID);
  });

  it("duas ações seguidas levam Idempotency-Key diferentes", async () => {
    const { m } = await abrir([OFERTA_DO_BRUNO, OFERTA_DA_CARLA]);
    const doBruno = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });
    const daCarla = oferta("carla_03", "ana_01");

    fireEvent.click(within(doBruno).getByRole("button", { name: "Recusar" }));
    await within(doBruno).findByText("Recusada");
    fireEvent.click(within(daCarla).getByRole("button", { name: "Recusar" }));
    await within(daCarla).findByText("Recusada");

    const chaveA = m.callsTo(ACAO("o1", "decline"))[0]!.headers["Idempotency-Key"];
    const chaveB = m.callsTo(ACAO("o2", "decline"))[0]!.headers["Idempotency-Key"];
    expect(chaveA).toMatch(UUID);
    expect(chaveB).toMatch(UUID);
    expect(chaveA).not.toBe(chaveB);
  });

  it("enquanto uma ação corre, os botões de todas as ofertas ficam desabilitados", async () => {
    let liberar: () => void = () => undefined;
    const espera = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    await abrir([OFERTA_DO_BRUNO, OFERTA_DA_CARLA], {
      [ACAO("o1", "decline")]: {
        status: 200,
        body: { ...OFERTA_DO_BRUNO, status: "declined", resolved_at: "2026-11-28T12:00:00Z" },
        wait: espera,
      },
    });
    const doBruno = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });
    const daCarla = oferta("carla_03", "ana_01");

    fireEvent.click(within(doBruno).getByRole("button", { name: "Recusar" }));

    await waitFor(() => {
      expect(within(daCarla).getByRole("button", { name: "Recusar" })).toBeDisabled();
    });
    expect(
      within(daCarla).getByRole("button", { name: "Aceitar oferta de carla_03" }),
    ).toBeDisabled();
    liberar();
    await waitFor(() => {
      expect(within(daCarla).getByRole("button", { name: "Recusar" })).toBeEnabled();
    });
  });

  // --- erros ----------------------------------------------------------------------------------

  it.each([
    [409, { code: "offer_not_pending" }, MUDOU],
    [404, { code: "offer_not_found" }, MUDOU],
    [409, { code: "player_unavailable" }, "Esse jogador não está disponível para esta ação."],
    [409, { code: "not_friends" }, "Vocês não são mais amigos."],
    [409, { code: "item_not_owned" }, "Um dos itens não está mais disponível."],
    [409, { code: "item_consumed" }, "Um dos itens não está mais disponível."],
    [409, { code: "item_already_offered" }, "Um dos itens não está mais disponível."],
    [429, { detail: "Request was throttled." }, "Muitas ações seguidas. Espere um pouco."],
    [500, { code: "qualquer", message: "Texto do servidor" }, FALHOU],
  ])("recusar com %i %o mostra '%s', recarrega a lista e não repete o texto do servidor", async (status, corpo, texto) => {
    const { m } = await abrir([OFERTA_DO_BRUNO], {
      [ACAO("o1", "decline")]: {
        status,
        body: { message: "Texto do servidor que não deve aparecer", ...corpo },
      },
    });
    const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

    fireEvent.click(within(card).getByRole("button", { name: "Recusar" }));

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent(texto);
    expect(aviso).not.toHaveTextContent("Texto do servidor");
    await waitFor(() => expect(m.callsTo(TRADES(1)).length).toBeGreaterThanOrEqual(2));
  });

  it("nenhuma mensagem de erro conta que a conta está desativada ou bloqueada", async () => {
    const proibidas = /desativ|bloquead/i;
    for (const code of ["player_unavailable", "not_friends"]) {
      const { m, unmount } = await abrir([OFERTA_DO_BRUNO], {
        [ACAO("o1", "decline")]: { status: 409, body: { code, message: "x" } },
      });
      const card = await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });

      fireEvent.click(within(card).getByRole("button", { name: "Recusar" }));

      expect(await screen.findByRole("alert")).not.toHaveTextContent(proibidas);
      expect(m.callsTo(ACAO("o1", "decline"))).toHaveLength(1);
      unmount();
    }
  });

  // --- sessão ---------------------------------------------------------------------------------

  it("ao sair, as ofertas de quem saiu são removidas do cache", async () => {
    const { client } = await abrir([OFERTA_DO_BRUNO]);
    await screen.findByRole("article", { name: "Oferta de bruno_02 para ana_01" });
    expect(client.getQueryCache().findAll({ queryKey: TRADES_ROOT_KEY }).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await waitFor(() => {
      expect(client.getQueryCache().findAll({ queryKey: TRADES_ROOT_KEY })).toHaveLength(0);
    });
  });
});
