export interface ApiErrorBody {
  error?: { code: string; message: string; request_id?: string };
}

export interface EndpointResult {
  path: string;
  ok: boolean;
  httpStatus: number | null;
  latencyMs: number;
  requestId: string | null;
  body: unknown;
  /** Present when the request failed or returned a non-2xx status. */
  failure: string | null;
}

const API_BASE = "/api/v1";
const UNREACHABLE = "The API is unreachable. Check that the backend is running.";

/**
 * Calls one API endpoint and reports exactly what happened.
 * Network failures and non-2xx responses become a described failure, never a thrown error,
 * so the UI can show real state instead of guessing.
 */
export async function probe(path: string, signal?: AbortSignal): Promise<EndpointResult> {
  const started = performance.now();
  try {
    const res = await fetch(`${API_BASE}${path}`, { signal });
    const latencyMs = Math.round(performance.now() - started);
    const requestId = res.headers.get("X-Request-ID");
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (res.ok) {
      return { path, ok: true, httpStatus: res.status, latencyMs, requestId, body, failure: null };
    }
    const apiMessage = (body as ApiErrorBody | null)?.error?.message;
    // A 5xx with no NEXUS error body came from a proxy or gateway, not from the API itself.
    const message = apiMessage ?? (res.status >= 500 ? UNREACHABLE : res.statusText);
    return {
      path,
      ok: false,
      httpStatus: res.status,
      latencyMs,
      requestId,
      body,
      failure: message || `HTTP ${res.status}`,
    };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    return {
      path,
      ok: false,
      httpStatus: null,
      latencyMs: Math.round(performance.now() - started),
      requestId: null,
      body: null,
      failure: UNREACHABLE,
    };
  }
}
