import { describe, expect, it } from "vitest";

import { mockFetch } from "../test/fetchMock";
import { ApiError, request } from "./http";

const CONFIG = "GET /_allauth/browser/v1/config";

describe("request", () => {
  it("GET não envia X-CSRFToken e usa credentials same-origin", async () => {
    document.cookie = "csrftoken=abc";
    const m = mockFetch({ "GET /api/v1/me/": { status: 200, body: { ok: true } } });

    await request("/api/v1/me/");

    const call = m.calls[0]!;
    expect(call.headers["X-CSRFToken"]).toBeUndefined();
    expect(call.credentials).toBe("same-origin");
  });

  it.each(["POST", "PATCH", "DELETE"] as const)(
    "%s envia o token do cookie em X-CSRFToken e o corpo como JSON",
    async (method) => {
      document.cookie = "csrftoken=abc";
      const m = mockFetch({ [`${method} /x`]: { status: 200, body: {} } });

      await request("/x", { method, body: { a: 1 } });

      const call = m.calls[0]!;
      expect(call.headers["X-CSRFToken"]).toBe("abc");
      expect(call.headers["Content-Type"]).toBe("application/json");
      expect(call.body).toEqual({ a: 1 });
    },
  );

  it("sem cookie de CSRF, busca /config antes e depois usa o token recebido", async () => {
    const m = mockFetch({
      [CONFIG]: () => {
        document.cookie = "csrftoken=fresh";
        return { status: 200, body: {} };
      },
      "POST /x": { status: 200, body: {} },
    });

    await request("/x", { method: "POST", body: {} });

    expect(m.calls.map((c) => `${c.method} ${c.url}`)).toEqual([CONFIG, "POST /x"]);
    expect(m.calls[1]!.headers["X-CSRFToken"]).toBe("fresh");
  });

  it("devolve o JSON da resposta em caso de sucesso", async () => {
    mockFetch({ "GET /x": { status: 200, body: { nome: "ana" } } });

    await expect(request("/x")).resolves.toEqual({ nome: "ana" });
  });

  it("400 vira ApiError com os erros separados por campo", async () => {
    document.cookie = "csrftoken=abc";
    mockFetch({
      "POST /x": {
        status: 400,
        body: {
          status: 400,
          errors: [
            { message: "Já existe", code: "unique", param: "username" },
            { message: "Geral", code: "invalid" },
          ],
        },
      },
    });

    const erro = await request("/x", { method: "POST", body: {} }).catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ApiError);
    expect(erro).toMatchObject({
      status: 400,
      fieldErrors: { username: ["Já existe"] },
      nonFieldErrors: ["Geral"],
    });
  });
});
