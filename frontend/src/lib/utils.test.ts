import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn", () => {
  it("junta classes e ignora valores falsos", () => {
    expect(cn("a", false, undefined, "b")).toBe("a b");
  });

  it("resolve conflito do Tailwind: a última classe vence", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});
