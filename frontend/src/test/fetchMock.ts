import { vi } from "vitest";

export interface RecordedCall {
  method: string;
  url: string;
  headers: Record<string, string>;
  body: unknown;
  credentials: RequestCredentials | undefined;
}

export interface MockReply {
  status: number;
  body?: unknown;
}

export type MockHandler = MockReply | ((call: RecordedCall) => MockReply);

/**
 * Substitui o `fetch` global. As rotas são "MÉTODO url" → resposta (ou função que a calcula).
 * Chamada sem rota simulada falha o teste: nada de requisição de rede "por acidente".
 */
export function mockFetch(routes: Record<string, MockHandler>) {
  const calls: RecordedCall[] = [];

  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const call: RecordedCall = {
      method,
      url,
      headers: (init?.headers ?? {}) as Record<string, string>,
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      credentials: init?.credentials,
    };
    calls.push(call);

    const handler = routes[`${method} ${url}`];
    if (!handler) {
      throw new Error(`fetch não simulado: ${method} ${url}`);
    }
    const reply = typeof handler === "function" ? handler(call) : handler;
    return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
      status: reply.status,
      headers: { "Content-Type": "application/json" },
    });
  });

  vi.stubGlobal("fetch", fn);

  return {
    fn,
    calls,
    callsTo: (key: string) => calls.filter((c) => `${c.method} ${c.url}` === key),
  };
}
