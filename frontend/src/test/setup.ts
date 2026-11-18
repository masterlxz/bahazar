import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Sem `globals: true` no Vitest, o RTL não limpa o DOM sozinho entre os testes.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // Zera o cookie de CSRF para um teste não herdar o token de outro.
  document.cookie = "csrftoken=; Max-Age=0; path=/";
});
