import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import App from "../App";

/** Renderiza o app inteiro numa rota, com um cache novo (sem retry, para o teste não demorar). */
export function renderApp(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const resultado = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // `client` permite ao teste olhar o cache (ex.: dado de um usuário que saiu).
  return { ...resultado, client };
}

/** Renderiza um componente isolado com QueryClientProvider e MemoryRouter (para testes de unidade). */
export function renderComponent(ui: React.ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const resultado = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
    options,
  );
  return { ...resultado, client };
}
