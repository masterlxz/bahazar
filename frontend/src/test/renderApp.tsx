import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
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

/** Renderiza um componente isolado (sem roteamento), com QueryClientProvider. */
export function renderComponent(component: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {component}
    </QueryClientProvider>,
  );
}
