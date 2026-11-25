import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockFetch, type MockHandler } from "../../../test/fetchMock";
import { FACETS, pagina } from "../../../test/fixtures";
import { renderApp } from "../../../test/renderApp";

describe("SkinsPage: catálogo /skins", () => {
  const SKIN_AK = {
    id: "k1",
    name: "Redline",
    weapon: "AK-47",
    rarity: "Classified",
    collection: "Phoenix",
    image_url: null,
    image_source: "none",
  };

  const SKIN_AWP = {
    id: "k2",
    name: "Asiimov",
    weapon: "AWP",
    rarity: "Covert",
    collection: "Dust",
    image_url: null,
    image_source: "none",
  };

  const SKIN_P250 = {
    id: "k3",
    name: "Sand Dune",
    weapon: "P250",
    rarity: "Consumer Grade",
    collection: "",
    image_url: null,
    image_source: "none",
  };

  const catalogRoute = (query: Record<string, string> = {}) => {
    const base = "/api/v1/catalog/";
    const texto = new URLSearchParams(query).toString();
    return `GET ${base}${texto ? `?${texto}` : ""}`;
  };

  const SESSION = "GET /_allauth/browser/v1/auth/session";
  const SESSION_AUTENTICADA = {
    status: 200,
    data: {
      user: {
        id: "u1",
        display: "ana_01",
        username: "ana_01",
        email: "ana@exemplo.com",
        has_usable_password: true,
      },
      methods: [],
    },
    meta: { is_authenticated: true },
  };

  function simular(rotas: Record<string, MockHandler>) {
    return mockFetch({
      [SESSION]: { status: 200, body: SESSION_AUTENTICADA },
      "GET /api/v1/catalog/facets/": { status: 200, body: FACETS },
      [catalogRoute()]: { status: 200, body: pagina([SKIN_AK, SKIN_AWP, SKIN_P250]) },
      ...rotas,
    });
  }

  const lista = () => within(screen.getByRole("list", { name: "Skins do catálogo" })).queryAllByRole("listitem");

  it("sem sessão, /skins redireciona para /entrar", async () => {
    mockFetch({
      [SESSION]: { status: 401, body: { status: 401, data: { flows: [] }, meta: { is_authenticated: false } } },
    });

    renderApp("/skins");

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Catálogo de Skins" })).not.toBeInTheDocument();
  });

  it("lista as skins com placeholder colorido por raridade e contagem total do servidor", async () => {
    const m = simular({});

    renderApp("/skins");

    expect(await screen.findByRole("heading", { name: "Catálogo de Skins" })).toBeInTheDocument();
    await screen.findByRole("list", { name: "Skins do catálogo" });
    expect(lista()).toHaveLength(3);
    const [ak, awp, p250] = lista();
    expect(within(ak!).getByText("Redline")).toBeInTheDocument();
    expect(within(ak!).getByText("AK-47")).toBeInTheDocument();
    expect(within(ak!).getByText("classified")).toBeInTheDocument();
    expect(within(ak!).getByText("Phoenix")).toBeInTheDocument();
    expect(within(awp!).getByText("Asiimov")).toBeInTheDocument();
    expect(within(awp!).getByText("covert")).toBeInTheDocument();
    expect(within(awp!).getByText("Dust")).toBeInTheDocument();
    expect(within(p250!).getByText("Sand Dune")).toBeInTheDocument();
    expect(within(p250!).getByText("consumer grade")).toBeInTheDocument();
    expect(screen.getByText("3 skins")).toBeInTheDocument();
    expect(m.callsTo(catalogRoute())).toHaveLength(1);
  });

  it("o total vem do servidor, não do tamanho da página", async () => {
    simular({
      [catalogRoute()]: { status: 200, body: pagina([SKIN_AK], { count: 30 }) },
    });

    renderApp("/skins");

    expect(await screen.findByText("30 skins")).toBeInTheDocument();
    expect(lista()).toHaveLength(1);
  });

  it("catálogo vazio mostra mensagem em vez de lista", async () => {
    simular({ [catalogRoute()]: { status: 200, body: pagina([]) } });

    renderApp("/skins");

    expect(await screen.findByText("Nenhuma skin encontrada.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Skins do catálogo" })).not.toBeInTheDocument();
  });

  it("enquanto carrega, mostra estado de carregamento", async () => {
    let liberar!: () => void;
    const espera = new Promise<void>((resolve) => (liberar = resolve));
    simular({ [catalogRoute()]: { status: 200, body: pagina([SKIN_AK]), wait: espera } });

    renderApp("/skins");

    expect(await screen.findByRole("status")).toHaveTextContent("Carregando catálogo…");
    expect(screen.queryByRole("list", { name: "Skins do catálogo" })).not.toBeInTheDocument();
    liberar();
    expect(await screen.findByText("Redline")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("falha do servidor (5xx) é tentada de novo, até 3 vezes, e só então mostra aviso", async () => {
    const m = simular({ [catalogRoute()]: { status: 500 } });

    renderApp("/skins");

    expect(await screen.findByRole("alert", {}, { timeout: 12_000 })).toHaveTextContent("Não foi possível carregar o catálogo. Tente novamente.");
    expect(m.callsTo(catalogRoute())).toHaveLength(4);
  }, 20_000);

  describe("filtros, ordenação e paginação", () => {
    it("Aplicar monta a query com raridade, arma, coleção, desgaste e busca (sem espaços nas pontas)", async () => {
      const m = simular({
        [catalogRoute({
          rarity: "Covert",
          weapon: "AWP",
          collection: "Dust",
          wear: "Factory New",
          q: "asiimov",
        })]: { status: 200, body: pagina([SKIN_AWP]) },
      });

      renderApp("/skins");
      await screen.findByText("Redline");

      await waitFor(() => expect(screen.getByLabelText("Raridade")).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText("Raridade"), { target: { value: "Covert" } });
      fireEvent.change(screen.getByLabelText("Arma"), { target: { value: "AWP" } });
      fireEvent.change(screen.getByLabelText("Coleção"), { target: { value: "Dust" } });
      fireEvent.change(screen.getByLabelText("Desgaste"), { target: { value: "Factory New" } });
      fireEvent.change(screen.getByLabelText("Buscar por nome"), { target: { value: "  asiimov  " } });
      fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

      expect(await screen.findByText("Asiimov")).toBeInTheDocument();
      expect(screen.queryByText("Redline")).not.toBeInTheDocument();
      expect(m.callsTo(catalogRoute({
        rarity: "Covert",
        weapon: "AWP",
        collection: "Dust",
        wear: "Factory New",
        q: "asiimov",
      }))).toHaveLength(1);
    });

    it("a busca aceita no máximo 50 caracteres", async () => {
      simular({});
      renderApp("/skins");
      await screen.findByText("Redline");

      expect(screen.getByLabelText("Buscar por nome")).toHaveAttribute("maxlength", "50");
    });

    it("o filtro de desgaste oferece exatamente os cinco desgastes do servidor, mais 'Todos'", async () => {
      simular({});
      renderApp("/skins");
      await screen.findByText("Redline");

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

    it("escolher a ordenação envia `ordering` com o prefixo '-' para decrescente", async () => {
      const m = simular({
        [catalogRoute({ ordering: "-price" })]: {
          status: 200,
          body: pagina([SKIN_P250, SKIN_AK, SKIN_AWP]),
        },
      });

      renderApp("/skins");
      await screen.findByText("Redline");

      fireEvent.change(screen.getByLabelText("Ordenar por"), { target: { value: "-price" } });
      fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

      expect(await screen.findByText("Sand Dune")).toBeInTheDocument();
      expect(m.callsTo(catalogRoute({ ordering: "-price" }))).toHaveLength(1);
    });

    it("Próxima e Anterior trocam de página e os botões respeitam o `next`/`previous` do servidor", async () => {
      const m = simular({
        [catalogRoute()]: {
          status: 200,
          body: pagina([SKIN_AK], { count: 30, next: "http://localhost/api/v1/catalog/?page=2" }),
        },
        [catalogRoute({ page: "2" })]: {
          status: 200,
          body: pagina([SKIN_AWP], { count: 30, previous: "http://localhost/api/v1/catalog/" }),
        },
      });

      renderApp("/skins");
      await screen.findByText("Redline");
      expect(screen.getByText("Página 1")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

      fireEvent.click(screen.getByRole("button", { name: "Próxima" }));

      expect(await screen.findByText("Asiimov")).toBeInTheDocument();
      expect(screen.getByText("Página 2")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
      expect(m.callsTo(catalogRoute({ page: "2" }))).toHaveLength(1);

      fireEvent.click(screen.getByRole("button", { name: "Anterior" }));

      expect(await screen.findByText("Redline")).toBeInTheDocument();
      expect(screen.getByText("Página 1")).toBeInTheDocument();
    });

    it("mudar um filtro volta para a primeira página (a query não leva `page`)", async () => {
      const m = simular({
        [catalogRoute({ page: "2" })]: {
          status: 200,
          body: pagina([SKIN_AWP], { count: 30, previous: "http://localhost/api/v1/catalog/" }),
        },
        [catalogRoute({ wear: "Minimal Wear" })]: { status: 200, body: pagina([SKIN_AK]) },
      });

      renderApp("/skins?page=2");
      await screen.findByText("Asiimov");
      expect(screen.getByText("Página 2")).toBeInTheDocument();

      fireEvent.change(screen.getByLabelText("Desgaste"), { target: { value: "Minimal Wear" } });
      fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

      expect(await screen.findByText("Redline")).toBeInTheDocument();
      expect(m.callsTo(catalogRoute({ wear: "Minimal Wear" }))).toHaveLength(1);
    });

    it("os filtros da URL já vêm preenchidos e são enviados ao servidor", async () => {
      const m = simular({
        [catalogRoute({ weapon: "AWP", ordering: "name" })]: {
          status: 200,
          body: pagina([SKIN_AWP]),
        },
      });

      renderApp("/skins?weapon=AWP&ordering=name");

      expect(await screen.findByText("Asiimov")).toBeInTheDocument();
      expect(screen.getByLabelText("Arma")).toHaveValue("AWP");
      expect(screen.getByLabelText("Ordenar por")).toHaveValue("name");
      expect(m.callsTo(catalogRoute({ weapon: "AWP", ordering: "name" }))).toHaveLength(1);
    });

    it("Limpar filtros volta à rota pura", async () => {
      const m = simular({
        [catalogRoute({ wear: "Well-Worn" })]: { status: 200, body: pagina([SKIN_AWP]) },
        [catalogRoute()]: { status: 200, body: pagina([SKIN_AK, SKIN_AWP, SKIN_P250]) },
      });

      renderApp("/skins?wear=Well-Worn");
      await screen.findByText("Asiimov");
      expect(screen.queryByText("Redline")).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));

      expect(await screen.findByText("Redline")).toBeInTheDocument();
      expect(screen.getByLabelText("Desgaste")).toHaveValue("");
      expect(m.callsTo(catalogRoute())).toHaveLength(1);
    });
  });

  describe("erros do servidor", () => {
    it("um 400 (filtro inválido, ex.: URL editada à mão) não quebra a tela e dá como se recuperar", async () => {
      const m = simular({
        [catalogRoute({ wear: "Quebrado" })]: {
          status: 400,
          body: { wear: ['"Quebrado" is not a valid choice.'] },
        },
        [catalogRoute()]: { status: 200, body: pagina([SKIN_AK]) },
      });

      renderApp("/skins?wear=Quebrado");

      expect(await screen.findByRole("alert")).toHaveTextContent("Algum filtro é inválido. Revise ou limpe os filtros.");
      expect(m.callsTo(catalogRoute({ wear: "Quebrado" }))).toHaveLength(1);
      expect(screen.getByRole("heading", { name: "Catálogo de Skins" })).toBeInTheDocument();
      expect(screen.getByLabelText("Desgaste")).toHaveValue("");
      expect(screen.queryByRole("list", { name: "Skins do catálogo" })).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));

      expect(await screen.findByText("Redline")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  describe("placeholder por raridade (Consumer=cinza, Industrial=azul-claro, Mil-Spec=azul, Restricted=roxo, Classified=rosa, Covert=vermelho, Contraband=laranja)", () => {
    it("cada raridade tem sua cor no placeholder", async () => {
      const SKINS_POR_RARIDADE = [
        { ...SKIN_AK, id: "c1", name: "Consumer", rarity: "Consumer Grade" as const },
        { ...SKIN_AK, id: "c2", name: "Industrial", rarity: "Industrial Grade" as const },
        { ...SKIN_AK, id: "c3", name: "MilSpec", rarity: "Mil-Spec Grade" as const },
        { ...SKIN_AK, id: "c4", name: "Restricted", rarity: "Restricted" as const },
        { ...SKIN_AK, id: "c5", name: "Classified", rarity: "Classified" as const },
        { ...SKIN_AK, id: "c6", name: "Covert", rarity: "Covert" as const },
        { ...SKIN_AK, id: "c7", name: "Contraband", rarity: "Contraband" as const },
      ];

      simular({
        [catalogRoute()]: { status: 200, body: pagina(SKINS_POR_RARIDADE) },
      });

      renderApp("/skins");
      await screen.findByText("Consumer");

      await waitFor(() => {
        const placeholders = screen.getAllByRole("img", { name: /placeholder da skin/i });
        expect(placeholders).toHaveLength(7);
        expect(placeholders[0]).toHaveClass("bg-neutral-500");   // Consumer Grade
        expect(placeholders[1]).toHaveClass("bg-sky-400");        // Industrial Grade
        expect(placeholders[2]).toHaveClass("bg-blue-500");       // Mil-Spec Grade
        expect(placeholders[3]).toHaveClass("bg-purple-500");     // Restricted
        expect(placeholders[4]).toHaveClass("bg-pink-500");       // Classified
        expect(placeholders[5]).toHaveClass("bg-red-500");        // Covert
        expect(placeholders[6]).toHaveClass("bg-orange-500");     // Contraband
      });
    });
  });
});