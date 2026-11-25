import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockFetch, type MockHandler } from "../../test/fetchMock";
import {
  BLOCKS,
  CARLA,
  ERRO_NAO_ENCONTRADO,
  FACETS,
  FRIENDS,
  ITEM_AK,
  ITEM_AWP,
  ITEM_BARATO,
  ITEM_DA_CARLA,
  LOGOUT,
  REQUESTS,
  SENT,
  SESSION,
  SESSION_ANONIMA,
  SESSION_AUTENTICADA,
  inventoryRoute,
  pagina,
} from "../../test/fixtures";
import { renderApp } from "../../test/renderApp";

beforeEach(() => {
  document.cookie = "csrftoken=tok";
});

const NAO_ENCONTRADO = "Inventário não encontrado.";
const FILTRO_INVALIDO = "Algum filtro é inválido. Revise ou limpe os filtros.";
const FALHOU = "Não foi possível carregar o inventário. Tente novamente.";

/** Sessão autenticada (com logout que a encerra) mais as rotas do teste. */
function simular(rotas: Record<string, MockHandler>) {
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
    "GET /api/v1/catalog/facets/": { status: 200, body: FACETS },
    ...rotas,
  });
}

const itens = () => within(screen.getByRole("list", { name: "Itens do inventário" }));
const lista = () => itens().queryAllByRole("listitem");

describe("InventoryPage: o meu inventário", () => {
  it("sem sessão, /inventario redireciona para /entrar", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    renderApp("/inventario");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Inventário" })).not.toBeInTheDocument();
  });

  it("lista os itens com desgaste e float do servidor e o preço formatado a partir dos centavos", async () => {
    const m = simular({
      [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK, ITEM_AWP, ITEM_BARATO]) },
    });

    renderApp("/inventario");

    expect(await screen.findByRole("heading", { name: "Inventário" })).toBeInTheDocument();
    await screen.findByRole("list", { name: "Itens do inventário" });
    const [ak, awp, barato] = lista();
    expect(lista()).toHaveLength(3);
    expect(within(ak!).getByText("Redline")).toBeInTheDocument();
    expect(within(ak!).getByText("AK-47")).toBeInTheDocument();
    expect(within(ak!).getByText("Classified")).toBeInTheDocument();
    expect(within(ak!).getByText("Field-Tested")).toBeInTheDocument();
    expect(within(ak!).getByText("Float 0.152300000")).toBeInTheDocument();
    expect(within(ak!).getByText(/US\$\s25,75/)).toBeInTheDocument();
    expect(within(awp!).getByText("Asiimov")).toBeInTheDocument();
    expect(within(awp!).getByText("Well-Worn")).toBeInTheDocument();
    expect(within(awp!).getByText(/US\$\s19,99/)).toBeInTheDocument();
    // 5 centavos: o cliente não faz conta, só formata o inteiro.
    expect(within(barato!).getByText(/US\$\s0,05/)).toBeInTheDocument();
    expect(screen.getByText("3 itens")).toBeInTheDocument();
    // Sem filtro nem página, a requisição é a rota pura, com a sessão (cookie) e só uma vez.
    expect(m.callsTo(inventoryRoute())).toHaveLength(1);
    expect(m.callsTo(inventoryRoute())[0]!.credentials).toBe("same-origin");
  });

  it("o total vem do servidor, não do tamanho da página", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK], { count: 30 }) } });

    renderApp("/inventario");

    expect(await screen.findByText("30 itens")).toBeInTheDocument();
    expect(lista()).toHaveLength(1);
  });

  it("inventário vazio mostra uma mensagem em vez de lista em branco", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([]) } });

    renderApp("/inventario");

    expect(await screen.findByText("Nenhum item encontrado.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Itens do inventário" })).not.toBeInTheDocument();
  });

  it("enquanto carrega, mostra o estado de carregamento", async () => {
    let liberar!: () => void;
    const espera = new Promise<void>((resolve) => (liberar = resolve));
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]), wait: espera } });

    renderApp("/inventario");

    expect(await screen.findByRole("status")).toHaveTextContent("Carregando inventário…");
    expect(screen.queryByRole("list", { name: "Itens do inventário" })).not.toBeInTheDocument();
    liberar();
    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("falha do servidor (5xx) é tentada de novo, até 3 vezes, e só então mostra o aviso", async () => {
    // O `retry` da consulta (4xx não repete, o resto sim) vale em vez do `retry: false` do
    // cliente dos testes, então aqui as esperas são as reais do TanStack (1 s + 2 s + 4 s).
    const m = simular({ [inventoryRoute()]: { status: 500 } });

    renderApp("/inventario");

    expect(await screen.findByRole("alert", {}, { timeout: 12_000 })).toHaveTextContent(FALHOU);
    expect(m.callsTo(inventoryRoute())).toHaveLength(4);
  }, 20_000);
});

describe("InventoryPage: filtros, ordenação e paginação", () => {
  it("Aplicar monta a query com raridade, arma, coleção, desgaste e busca (sem espaços nas pontas)", async () => {
    const m = simular({
      [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK, ITEM_AWP]) },
      [inventoryRoute({
        rarity: "Mil-Spec Grade",
        weapon: "AWP",
        collection: "Phoenix",
        wear: "Well-Worn",
        q: "dune",
      })]: { status: 200, body: pagina([ITEM_BARATO]) },
    });
    renderApp("/inventario");
    await screen.findByText("Redline");

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText("Arma")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText("Coleção")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText("Desgaste")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText("Buscar por nome")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Raridade"), { target: { value: "Mil-Spec Grade" } });
    fireEvent.change(screen.getByLabelText("Arma"), { target: { value: "AWP" } });
    fireEvent.change(screen.getByLabelText("Coleção"), { target: { value: "Phoenix" } });
    fireEvent.change(screen.getByLabelText("Desgaste"), { target: { value: "Well-Worn" } });
    fireEvent.change(screen.getByLabelText("Buscar por nome"), { target: { value: "  dune " } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(await screen.findByText("Sand Dune")).toBeInTheDocument();
    expect(screen.queryByText("Redline")).not.toBeInTheDocument();
    expect(
      m.callsTo(
        inventoryRoute({ rarity: "Mil-Spec Grade", weapon: "AWP", collection: "Phoenix", wear: "Well-Worn", q: "dune" }),
      ),
    ).toHaveLength(1);
  });

  it("a busca aceita no máximo 50 caracteres, como o servidor", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });
    renderApp("/inventario");
    await screen.findByText("Redline");

    expect(screen.getByLabelText("Buscar por nome")).toHaveAttribute("maxlength", "50");
  });

  it("o filtro de desgaste oferece exatamente os cinco desgastes do servidor, mais 'Todos'", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });
    renderApp("/inventario");
    await screen.findByText("Redline");

    await waitFor(() => expect(screen.getByLabelText("Desgaste")).toBeInTheDocument());

    const opcoes = within(screen.getByLabelText("Desgaste")).getAllByRole("option");

    expect(opcoes.map((o) => o.textContent)).toEqual([
      "Todos",
      "Factory New",
      "Minimal Wear",
      "Field-Tested",
      "Well-Worn",
      "Battle-Scarred",
    ]);
  });

  it("o filtro de raridade oferece as raridades das facets", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });
    renderApp("/inventario");
    await screen.findByText("Redline");

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());

    const opcoes = within(screen.getByLabelText("Raridade")).getAllByRole("option");
    expect(opcoes.map((o) => o.textContent)).toEqual([
      "Todas",
      "Consumer Grade",
      "Industrial Grade",
      "Mil-Spec Grade",
      "Restricted",
      "Classified",
      "Covert",
      "Contraband",
    ]);
  });

  it("o filtro de arma oferece as armas das facets", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });
    renderApp("/inventario");
    await screen.findByText("Redline");

    await waitFor(() => expect(screen.getByLabelText("Arma")).toBeInTheDocument());

    const opcoes = within(screen.getByLabelText("Arma")).getAllByRole("option");
    expect(opcoes.map((o) => o.textContent)).toEqual(["Todas", "AK-47", "AWP", "Glock-18", "M4A4", "P250"]);
  });

  it("o filtro de coleção oferece as coleções das facets", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });
    renderApp("/inventario");
    await screen.findByText("Redline");

    await waitFor(() => expect(screen.getByLabelText("Coleção")).toBeInTheDocument());

    const opcoes = within(screen.getByLabelText("Coleção")).getAllByRole("option");
    expect(opcoes.map((o) => o.textContent)).toEqual(["Todas", "Phoenix", "Dust", "Chroma", "Gamma"]);
  });

  it("usa as facets do catálogo para preencher os selects (raridade, arma, coleção, desgaste)", async () => {
    const m = simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });
    renderApp("/inventario");
    await screen.findByText("Redline");

    await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());

    const raridade = within(screen.getByLabelText("Raridade")).getAllByRole("option");
    expect(raridade.map((o) => o.textContent)).toEqual([
      "Todas",
      "Consumer Grade",
      "Industrial Grade",
      "Mil-Spec Grade",
      "Restricted",
      "Classified",
      "Covert",
      "Contraband",
    ]);

    const arma = within(screen.getByLabelText("Arma")).getAllByRole("option");
    expect(arma.map((o) => o.textContent)).toEqual(["Todas", "AK-47", "AWP", "Glock-18", "M4A4", "P250"]);

    const colecao = within(screen.getByLabelText("Coleção")).getAllByRole("option");
    expect(colecao.map((o) => o.textContent)).toEqual(["Todas", "Phoenix", "Dust", "Chroma", "Gamma"]);

    const desgaste = within(screen.getByLabelText("Desgaste")).getAllByRole("option");
    expect(desgaste.map((o) => o.textContent)).toEqual([
      "Todos",
      "Factory New",
      "Minimal Wear",
      "Field-Tested",
      "Well-Worn",
      "Battle-Scarred",
    ]);

    expect(m.callsTo("GET /api/v1/catalog/facets/")).toHaveLength(1);
  });

  it("escolher a ordenação envia `ordering` com o prefixo '-' para decrescente", async () => {
    const m = simular({
      [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK, ITEM_AWP]) },
      [inventoryRoute({ ordering: "-price" })]: {
        status: 200,
        body: pagina([ITEM_AK, ITEM_AWP, ITEM_BARATO]),
      },
    });
    renderApp("/inventario");
    await screen.findByText("Redline");

    fireEvent.change(screen.getByLabelText("Ordenar por"), { target: { value: "-price" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(await screen.findByText("Sand Dune")).toBeInTheDocument();
    expect(m.callsTo(inventoryRoute({ ordering: "-price" }))).toHaveLength(1);
  });

  it("Próxima e Anterior trocam de página e os botões respeitam o `next`/`previous` do servidor", async () => {
    const m = simular({
      [inventoryRoute()]: {
        status: 200,
        body: pagina([ITEM_AK], { count: 30, next: "http://localhost/api/v1/inventory/?page=2" }),
      },
      [inventoryRoute({ page: "2" })]: {
        status: 200,
        body: pagina([ITEM_AWP], { count: 30, previous: "http://localhost/api/v1/inventory/" }),
      },
    });
    renderApp("/inventario");
    await screen.findByText("Redline");
    expect(screen.getByText("Página 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Próxima" }));

    expect(await screen.findByText("Asiimov")).toBeInTheDocument();
    expect(screen.getByText("Página 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
    expect(m.callsTo(inventoryRoute({ page: "2" }))).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Anterior" }));

    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(screen.getByText("Página 1")).toBeInTheDocument();
  });

  it("mudar um filtro volta para a primeira página (a query não leva `page`)", async () => {
    const m = simular({
      [inventoryRoute({ page: "2" })]: {
        status: 200,
        body: pagina([ITEM_AWP], { count: 30, previous: "http://localhost/api/v1/inventory/" }),
      },
      [inventoryRoute({ wear: "Minimal Wear" })]: { status: 200, body: pagina([ITEM_AK]) },
    });
    renderApp("/inventario?page=2");
    await screen.findByText("Asiimov");
    expect(screen.getByText("Página 2")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Desgaste"), { target: { value: "Minimal Wear" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(m.callsTo(inventoryRoute({ wear: "Minimal Wear" }))).toHaveLength(1);
  });

  it("os filtros da URL já vêm preenchidos e são enviados ao servidor", async () => {
    const m = simular({
      [inventoryRoute({ weapon: "AWP", ordering: "name" })]: {
        status: 200,
        body: pagina([ITEM_AWP]),
      },
    });

    renderApp("/inventario?weapon=AWP&ordering=name");

    expect(await screen.findByText("Asiimov")).toBeInTheDocument();
    expect(screen.getByLabelText("Arma")).toHaveValue("AWP");
    expect(screen.getByLabelText("Ordenar por")).toHaveValue("name");
    expect(m.callsTo(inventoryRoute({ weapon: "AWP", ordering: "name" }))).toHaveLength(1);
  });

  it("Limpar filtros volta à rota pura", async () => {
    const m = simular({
      [inventoryRoute({ wear: "Well-Worn" })]: { status: 200, body: pagina([ITEM_AWP]) },
      [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK, ITEM_AWP]) },
    });
    renderApp("/inventario?wear=Well-Worn");
    await screen.findByText("Asiimov");
    expect(screen.queryByText("Redline")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));

    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(screen.getByLabelText("Desgaste")).toHaveValue("");
    expect(m.callsTo(inventoryRoute())).toHaveLength(1);
  });
});

describe("InventoryPage: erros do servidor", () => {
  it("um 400 (filtro inválido, ex.: URL editada à mão) não quebra a tela e dá como se recuperar", async () => {
    const m = simular({
      [inventoryRoute({ wear: "Quebrado" })]: {
        status: 400,
        body: { wear: ['"Quebrado" is not a valid choice.'] },
      },
      [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) },
    });

    renderApp("/inventario?wear=Quebrado");

    expect(await screen.findByRole("alert")).toHaveTextContent(FILTRO_INVALIDO);
    // A requisição com o valor ruim de fato saiu (é ela que o servidor recusou).
    expect(m.callsTo(inventoryRoute({ wear: "Quebrado" }))).toHaveLength(1);
    // A tela continua inteira: título, formulário e o select já sem o valor inválido.
    expect(screen.getByRole("heading", { name: "Inventário" })).toBeInTheDocument();
    expect(screen.getByLabelText("Desgaste")).toHaveValue("");
    expect(screen.queryByRole("list", { name: "Itens do inventário" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));

    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("uma página que não existe (404 em `page`) oferece voltar à primeira", async () => {
    simular({
      [inventoryRoute({ page: "9" })]: { status: 404, body: { detail: "Invalid page." } },
      [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) },
    });

    renderApp("/inventario?page=9");

    expect(await screen.findByRole("alert")).toHaveTextContent(NAO_ENCONTRADO);
    fireEvent.click(screen.getByRole("button", { name: "Voltar à primeira página" }));

    expect(await screen.findByText("Redline")).toBeInTheDocument();
  });

  it.each([
    [404, ERRO_NAO_ENCONTRADO, NAO_ENCONTRADO],
    [400, { wear: ['"x" is not a valid choice.'] }, FILTRO_INVALIDO],
  ])(
    "se um refetch passa a dar %i, os itens que já estavam na tela somem (o erro não convive com dado antigo)",
    async (status, corpo, mensagem) => {
      // O TanStack Query MANTÉM `data` quando um refetch falha. Caso real: o amigo me desfaz ou
      // bloqueia, e eu volto à tela com o cache anterior: a lista dele não pode continuar visível.
      let falhar = false;
      const m = simular({
        [inventoryRoute({}, "carla_03")]: () =>
          falhar
            ? { status, body: corpo }
            : { status: 200, body: pagina([ITEM_DA_CARLA], { count: 7 }) },
      });
      const { client } = renderApp("/inventario/carla_03");
      expect(await screen.findByText("Fade")).toBeInTheDocument();
      expect(screen.getByText("7 itens")).toBeInTheDocument();

      falhar = true;
      await act(async () => {
        await client.invalidateQueries({ queryKey: ["inventory"] });
      });

      expect(await screen.findByRole("alert")).toHaveTextContent(mensagem);
      // A premissa: houve mesmo um segundo GET, e foi ele que falhou.
      expect(m.callsTo(inventoryRoute({}, "carla_03"))).toHaveLength(2);
      expect(screen.queryByText("Fade")).not.toBeInTheDocument();
      expect(screen.queryByText("7 itens")).not.toBeInTheDocument();
      expect(screen.queryByRole("list", { name: "Itens do inventário" })).not.toBeInTheDocument();
      expect(screen.queryByRole("navigation", { name: "Paginação" })).not.toBeInTheDocument();
    },
  );

  it("um `page` que não é número é ignorado (a requisição vai sem ele)", async () => {
    const m = simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });

    renderApp("/inventario?page=abc");

    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(m.callsTo(inventoryRoute())).toHaveLength(1);
  });
});

describe("InventoryPage: inventário de um amigo", () => {
  it("/inventario/:username lista o inventário DAQUELE jogador, não o meu", async () => {
    const m = simular({
      [inventoryRoute({}, "carla_03")]: { status: 200, body: pagina([ITEM_DA_CARLA]) },
    });

    renderApp("/inventario/carla_03");

    expect(await screen.findByRole("heading", { name: "Inventário de carla_03" })).toBeInTheDocument();
    await screen.findByText("Fade");
    const [fade] = lista();
    expect(within(fade!).getByText("Fade")).toBeInTheDocument();
    expect(within(fade!).getByText("Factory New")).toBeInTheDocument();
    expect(within(fade!).getByText(/US\$\s410,00/)).toBeInTheDocument();
    expect(m.callsTo(inventoryRoute({}, "carla_03"))).toHaveLength(1);
    expect(m.calls.filter((c) => c.url === "/api/v1/inventory/")).toHaveLength(0);
  });

  it("os filtros valem também para o inventário do amigo", async () => {
    const m = simular({
      [inventoryRoute({}, "carla_03")]: { status: 200, body: pagina([ITEM_DA_CARLA]) },
      [inventoryRoute({ wear: "Factory New" }, "carla_03")]: {
        status: 200,
        body: pagina([ITEM_DA_CARLA]),
      },
    });
    renderApp("/inventario/carla_03");
    await screen.findByText("Fade");

    fireEvent.change(screen.getByLabelText("Desgaste"), { target: { value: "Factory New" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    await waitFor(() =>
      expect(m.callsTo(inventoryRoute({ wear: "Factory New" }, "carla_03"))).toHaveLength(1),
    );
  });

  it("o username da URL é codificado ao ir para a API", async () => {
    const m = simular({
      [inventoryRoute({}, "ana%20b")]: { status: 200, body: pagina([ITEM_DA_CARLA]) },
    });

    renderApp("/inventario/ana%20b");

    expect(await screen.findByRole("heading", { name: "Inventário de ana b" })).toBeInTheDocument();
    expect(await screen.findByText("Fade")).toBeInTheDocument();
    expect(m.callsTo(inventoryRoute({}, "ana%20b"))).toHaveLength(1);
  });

  it("o username de caminho especial (a/b?x#y) é codificado por inteiro, sem escapar do segmento", async () => {
    const m = simular({
      [inventoryRoute({}, "a%2Fb%3Fx%23y")]: { status: 200, body: pagina([ITEM_DA_CARLA]) },
    });

    renderApp("/inventario/a%2Fb%3Fx%23y");

    // A premissa: o roteador entregou o nome decodificado, e é a tela que o codifica para a API.
    expect(await screen.findByRole("heading", { name: "Inventário de a/b?x#y" })).toBeInTheDocument();
    expect(await screen.findByText("Fade")).toBeInTheDocument();
    expect(m.callsTo(inventoryRoute({}, "a%2Fb%3Fx%23y"))).toHaveLength(1);
  });

  it.each([".", ".."])("o username '%s' nunca vai à API: mostra a mensagem de não encontrado", async (username) => {
    // `/api/v1/inventory/../` seria normalizado pelo navegador para `/api/v1/`.
    const m = simular({});

    renderApp(`/inventario/${username}`);

    expect((await screen.findByRole("alert")).textContent).toBe(NAO_ENCONTRADO);
    expect(m.calls.filter((c) => c.url.startsWith("/api/v1/inventory"))).toHaveLength(0);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("o 404 mostra a mesma tela, palavra por palavra, qualquer que seja o jogador pedido", async () => {
    // O servidor devolve o mesmo 404 a não amigo, pendente, bloqueado e inexistente (o corpo
    // não diz o motivo); aqui só se prova o lado da tela: ela não acrescenta nada por jogador.
    async function textoDoNaoEncontrado(username: string) {
      const m = simular({
        [inventoryRoute({}, username)]: { status: 404, body: ERRO_NAO_ENCONTRADO },
      });
      const { container, unmount } = renderApp(`/inventario/${username}`);
      const alerta = await screen.findByRole("alert");
      expect(alerta.textContent).toBe(NAO_ENCONTRADO);
      expect(m.callsTo(inventoryRoute({}, username))).toHaveLength(1);
      expect(screen.queryByRole("list", { name: "Itens do inventário" })).not.toBeInTheDocument();
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
      // Sem "Voltar à primeira página": na página 1 não há para onde voltar.
      expect(
        screen.queryByRole("button", { name: "Voltar à primeira página" }),
      ).not.toBeInTheDocument();
      const texto = (container.textContent ?? "").replaceAll(username, "<jogador>");
      unmount();
      return texto;
    }

    const doNaoAmigo = await textoDoNaoEncontrado("nao_amigo");
    const doInexistente = await textoDoNaoEncontrado("fantasma_99");

    expect(doNaoAmigo).toContain("<jogador>");
    expect(doNaoAmigo).toBe(doInexistente);
  });

  it("a lista de amigos tem um link 'Inventário' para o inventário de cada amigo", async () => {
    simular({
      [FRIENDS]: { status: 200, body: [CARLA] },
      [REQUESTS]: { status: 200, body: [] },
      [SENT]: { status: 200, body: [] },
      [BLOCKS]: { status: 200, body: [] },
    });

    renderApp("/amigos");

    const link = await screen.findByRole("link", { name: "Inventário de carla_03" });
    expect(link).toHaveAttribute("href", "/inventario/carla_03");
    expect(link).toHaveTextContent("Inventário");
  });
});

describe("InventoryPage: cabeçalho e logout", () => {
  it("o cabeçalho de quem está logado tem o link Inventário", async () => {
    simular({ [inventoryRoute()]: { status: 200, body: pagina([ITEM_AK]) } });

    renderApp("/inventario");

    const link = await screen.findByRole("link", { name: "Inventário" });
    expect(link).toHaveAttribute("href", "/inventario");
  });

  it("ao sair, o inventário em cache (inclusive o de um amigo) é removido", async () => {
    simular({
      [inventoryRoute({}, "carla_03")]: { status: 200, body: pagina([ITEM_DA_CARLA]) },
    });
    const { client } = renderApp("/inventario/carla_03");
    await screen.findByText("Fade");
    // A chave raiz é ["inventory"]; a premissa é que há dado de inventário em cache antes de sair.
    expect(client.getQueryCache().findAll({ queryKey: ["inventory"] }).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Sair" }));

    await screen.findByRole("heading", { name: "Entrar" });
    expect(client.getQueryCache().findAll({ queryKey: ["inventory"] })).toHaveLength(0);
  });
});
