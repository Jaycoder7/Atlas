import { describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("api", () => {
  it("returns parsed JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } })));
    await expect(api<{ok:boolean}>("/health")).resolves.toEqual({ ok: true });
  });
  it("surfaces API failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad request", { status: 422 })));
    await expect(api("/broken")).rejects.toThrow("bad request");
  });
});

