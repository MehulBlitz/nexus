import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SystemStatus } from "@/features/dashboard/SystemStatus";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "X-Request-ID": "req-12345678" } });
}

function routeFetch(map: Record<string, () => Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const key = Object.keys(map).find((k) => String(url).endsWith(k));
      if (!key) throw new Error(`unexpected url ${url}`);
      return map[key]!();
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("SystemStatus", () => {
  it("shows a loading state first", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<SystemStatus />);
    expect(screen.getByText("Checking the API…")).toBeInTheDocument();
  });

  it("shows real results when everything passes", async () => {
    routeFetch({
      "/health": () => jsonResponse({ status: "ok" }),
      "/ready": () => jsonResponse({ status: "ready", checks: { database: "ok" } }),
      "/version": () => jsonResponse({ name: "NEXUS", version: "0.1.0", environment: "development" }),
    });
    render(<SystemStatus />);
    await waitFor(() => expect(screen.getByText(/All checks passing/)).toBeInTheDocument());
    expect(screen.getByText("NEXUS 0.1.0 (development)")).toBeInTheDocument();
    expect(screen.getAllByText("OK")).toHaveLength(3);
  });

  it("shows the failing check and the API's message", async () => {
    routeFetch({
      "/health": () => jsonResponse({ status: "ok" }),
      "/ready": () =>
        jsonResponse({ error: { code: "not_ready", message: "Service dependencies are unavailable" } }, 503),
      "/version": () => jsonResponse({ name: "NEXUS", version: "0.1.0", environment: "development" }),
    });
    render(<SystemStatus />);
    await waitFor(() => expect(screen.getByText("One or more checks failed")).toBeInTheDocument());
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Service dependencies are unavailable")).toBeInTheDocument();
  });

  it("re-runs the checks on request", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ status: "ok", name: "NEXUS", version: "0.1.0", environment: "test" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<SystemStatus />);
    await waitFor(() => expect(screen.getByText(/All checks passing/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await userEvent.click(screen.getByRole("button", { name: "Run checks again" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
  });
});
