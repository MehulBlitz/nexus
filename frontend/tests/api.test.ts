import { afterEach, describe, expect, it, vi } from "vitest";
import { probe } from "@/lib/api";

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => vi.unstubAllGlobals());

describe("probe", () => {
  it("reports success with request id and body", async () => {
    mockFetch(async () =>
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "X-Request-ID": "abc12345xyz" },
      }),
    );
    const r = await probe("/health");
    expect(r).toMatchObject({ ok: true, httpStatus: 200, requestId: "abc12345xyz", failure: null });
    expect(r.body).toEqual({ status: "ok" });
  });

  it("surfaces the API error message on non-2xx", async () => {
    mockFetch(async () =>
      new Response(JSON.stringify({ error: { code: "not_ready", message: "Service dependencies are unavailable" } }), {
        status: 503,
      }),
    );
    const r = await probe("/ready");
    expect(r.ok).toBe(false);
    expect(r.httpStatus).toBe(503);
    expect(r.failure).toBe("Service dependencies are unavailable");
  });

  it("describes an unreachable API instead of throwing", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const r = await probe("/health");
    expect(r.ok).toBe(false);
    expect(r.httpStatus).toBeNull();
    expect(r.failure).toMatch(/unreachable/i);
  });

  it("treats a 5xx without an API error body as unreachable (proxy or gateway failure)", async () => {
    mockFetch(async () => new Response("bad gateway", { status: 502, statusText: "Bad Gateway" }));
    const r = await probe("/health");
    expect(r.ok).toBe(false);
    expect(r.httpStatus).toBe(502);
    expect(r.failure).toMatch(/unreachable/i);
  });

  it("tolerates a non-JSON 4xx body using the status text", async () => {
    mockFetch(async () => new Response("nope", { status: 404, statusText: "Not Found" }));
    const r = await probe("/missing");
    expect(r.failure).toBe("Not Found");
  });
});
