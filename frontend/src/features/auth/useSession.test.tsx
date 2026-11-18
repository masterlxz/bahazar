import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { mockFetch } from "../../test/fetchMock";
import { SESSION, SESSION_ANONIMA, SESSION_AUTENTICADA } from "../../test/fixtures";
import { useSession } from "./useSession";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useSession", () => {
  it("401 é 'anônimo', não erro", async () => {
    mockFetch({ [SESSION]: { status: 401, body: SESSION_ANONIMA } });

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe("anonymous"));
    expect(result.current.user).toBeNull();
  });

  it("200 devolve o usuário autenticado", async () => {
    mockFetch({ [SESSION]: { status: 200, body: SESSION_AUTENTICADA } });

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.user).toEqual({
      id: "u1",
      username: "ana_01",
      email: "ana@exemplo.com",
    });
  });
});
