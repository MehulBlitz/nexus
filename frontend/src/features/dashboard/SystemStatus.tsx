import { useCallback, useEffect, useState } from "react";
import { probe, type EndpointResult } from "@/lib/api";

const CHECKS = [
  { path: "/health", label: "API process", detail: "Is the service running" },
  { path: "/ready", label: "Database", detail: "Can the service reach its database" },
  { path: "/version", label: "Build", detail: "Which version is deployed" },
] as const;

type State =
  | { phase: "loading" }
  | { phase: "done"; results: EndpointResult[]; checkedAt: Date };

function describe(result: EndpointResult): string {
  if (!result.ok) return result.failure ?? "Check failed";
  const body = result.body as Record<string, unknown> | null;
  if (result.path === "/version" && body) {
    return `${String(body.name)} ${String(body.version)} (${String(body.environment)})`;
  }
  return "Passing";
}

export function SystemStatus() {
  const [state, setState] = useState<State>({ phase: "loading" });

  const run = useCallback(async (signal?: AbortSignal) => {
    setState({ phase: "loading" });
    try {
      const results = await Promise.all(CHECKS.map((c) => probe(c.path, signal)));
      setState({ phase: "done", results, checkedAt: new Date() });
    } catch {
      // Aborted on unmount: nothing to render.
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void run(controller.signal);
    return () => controller.abort();
  }, [run]);

  const allPassing = state.phase === "done" && state.results.every((r) => r.ok);

  return (
    <section aria-labelledby="status-heading" className="rounded-lg border border-line bg-surface">
      <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
        <div>
          <h2 id="status-heading" className="text-base font-semibold">
            Service status
          </h2>
          <p className="mt-0.5 text-sm text-muted" role="status" aria-live="polite">
            {state.phase === "loading" && "Checking the API…"}
            {state.phase === "done" &&
              (allPassing
                ? `All checks passing at ${state.checkedAt.toLocaleTimeString()}`
                : "One or more checks failed")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void run()}
          disabled={state.phase === "loading"}
          className="rounded-md border border-line px-3 py-1.5 text-sm hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          Run checks again
        </button>
      </div>

      <ul className="divide-y divide-line">
        {CHECKS.map((check) => {
          const result = state.phase === "done" ? state.results.find((r) => r.path === check.path) : undefined;
          return (
            <li key={check.path} className="flex items-start justify-between gap-4 px-5 py-3.5">
              <div>
                <p className="text-sm font-medium">{check.label}</p>
                <p className="text-sm text-muted">{check.detail}</p>
              </div>
              <div className="text-right">
                {!result ? (
                  <p className="text-sm text-muted">Checking…</p>
                ) : (
                  <>
                    <p className={`text-sm font-medium ${result.ok ? "text-ok" : "text-fail"}`}>
                      {result.ok ? "OK" : "Failed"}
                    </p>
                    <p className="max-w-xs text-sm text-muted">{describe(result)}</p>
                    <p className="mt-1 font-mono text-xs text-muted">
                      {result.latencyMs} ms
                      {result.requestId ? ` · request ${result.requestId.slice(0, 8)}` : ""}
                    </p>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
