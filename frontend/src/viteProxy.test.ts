import { describe, expect, it } from "vitest";

import config from "../vite.config";

describe("proxy do servidor de desenvolvimento", () => {
  // Sem o proxy o navegador trataria o backend como outra origem e o cookie de sessão não iria.
  it("encaminha /api e /_allauth para o backend (porta 8000 por padrão)", () => {
    const proxy = config.server?.proxy as Record<string, { target: string }>;

    expect(Object.keys(proxy).sort()).toEqual(["/_allauth", "/api"]);
    expect(proxy["/api"]).toMatchObject({ target: "http://localhost:8000" });
    expect(proxy["/_allauth"]).toMatchObject({ target: "http://localhost:8000" });
  });
});
