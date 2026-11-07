import type {
  AgentDefinition,
  AgentRunGlobal,
  ApiToken,
  AuthResponse,
  DashboardStats,
  DependencyChain,
  FileEntry,
  GraphMetrics,
  GraphResponse,
  ImpactResult,
  Investigation,
  InvestigationDetail,
  Job,
  Page,
  Report,
  ReportDetail,
  Repository,
  RepositoryActivity,
  RepositoryDetail,
  RepositoryOverview,
  RepositoryStatusResponse,
  RiskFinding,
  RiskFindingDetail,
  RiskSummary,
  SearchHit,
  SymbolEntry,
  User,
} from "@/types/api";

const API_BASE = "/api/v1";
const UNREACHABLE = "The API is unreachable. Check that the backend is running.";

export interface ApiErrorBody {
  error?: { code: string; message: string; request_id?: string; details?: unknown };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: unknown;

  constructor(message: string, status: number, code: string, requestId: string | null, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)nexus_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]!) : null;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (!["GET", "HEAD"].includes(method)) {
    const token = csrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: "include",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(UNREACHABLE, 0, "unreachable", null);
  }
  const requestId = response.headers.get("X-Request-ID");
  if (response.status === 204) return undefined as T;
  let parsed: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }
  if (!response.ok) {
    const body = parsed as ApiErrorBody | null;
    const message =
      body?.error?.message ??
      (response.status >= 500 ? UNREACHABLE : response.statusText || `HTTP ${response.status}`);
    throw new ApiError(
      message,
      response.status,
      body?.error?.code ?? `http_${response.status}`,
      requestId,
      body?.error?.details,
    );
  }
  return parsed as T;
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  auth: {
    me: () => apiRequest<User>("/auth/me"),
    login: (email: string, password: string) =>
      apiRequest<AuthResponse>("/auth/login", { method: "POST", body: { email, password } }),
    register: (email: string, password: string, display_name: string) =>
      apiRequest<AuthResponse>("/auth/register", {
        method: "POST",
        body: { email, password, display_name },
      }),
    logout: () => apiRequest<void>("/auth/logout", { method: "POST" }),
    tokens: () => apiRequest<ApiToken[]>("/auth/tokens"),
    createToken: (name: string) =>
      apiRequest<{ token: string; record: ApiToken; warning: string }>("/auth/tokens", {
        method: "POST",
        body: { name },
      }),
    revokeToken: (id: string) =>
      apiRequest<void>(`/auth/tokens/${id}`, { method: "DELETE" }),
    changePassword: (current_password: string, new_password: string) =>
      apiRequest<void>("/auth/change-password", {
        method: "POST",
        body: { current_password, new_password },
      }),
    deleteAccount: (password: string) =>
      apiRequest<void>("/auth/account", {
        method: "POST",
        body: { password, confirm: "DELETE" },
      }),
  },
  dashboard: () => apiRequest<DashboardStats>("/dashboard"),
  jobs: (id: string) => apiRequest<Job>(`/jobs/${id}`),
  repositories: {
    list: (limit = 50, offset = 0) =>
      apiRequest<Page<Repository>>(`/repositories${query({ limit, offset })}`),
    import: (url: string, branch?: string, display_name?: string) =>
      apiRequest<RepositoryDetail>("/repositories", {
        method: "POST",
        body: { url, branch: branch || null, display_name: display_name || null },
      }),
    get: (id: string) => apiRequest<RepositoryDetail>(`/repositories/${id}`),
    remove: (id: string) => apiRequest<void>(`/repositories/${id}`, { method: "DELETE" }),
    index: (id: string) =>
      apiRequest<Job>(`/repositories/${id}/index`, { method: "POST" }),
    status: (id: string) => apiRequest<RepositoryStatusResponse>(`/repositories/${id}/status`),
    overview: (id: string) => apiRequest<RepositoryOverview>(`/repositories/${id}/overview`),
    activity: (id: string) => apiRequest<RepositoryActivity>(`/repositories/${id}/activity`),
    insights: (id: string) => apiRequest<Record<string, unknown>>(`/repositories/${id}/insights`),
    files: (id: string, limit = 100, offset = 0) =>
      apiRequest<Page<FileEntry>>(`/repositories/${id}/files${query({ limit, offset })}`),
    symbols: (id: string, q?: string, language?: string, limit = 100) =>
      apiRequest<Page<SymbolEntry>>(`/repositories/${id}/symbols${query({ q, language, limit })}`),
    search: (id: string, q: string, language?: string, directory?: string) =>
      apiRequest<SearchHit[]>(`/repositories/${id}/search${query({ q, language, directory })}`),
  },
  graph: {
    view: (
      id: string,
      params: { node_types?: string; relationship_types?: string; search?: string; limit?: number } = {},
    ) => apiRequest<GraphResponse>(`/repositories/${id}/graph${query(params)}`),
    metrics: (id: string) => apiRequest<GraphMetrics>(`/repositories/${id}/graph/metrics`),
    dependencies: (id: string, nodeId: string, direction: "dependencies" | "dependents", maxDepth = 3) =>
      apiRequest<DependencyChain>(
        `/repositories/${id}/graph/dependencies/${nodeId}${query({ direction, max_depth: maxDepth })}`,
      ),
    impact: (id: string, node_id: string, direction = "dependents", max_depth = 4) =>
      apiRequest<ImpactResult>(`/repositories/${id}/graph/impact`, {
        method: "POST",
        body: { node_id, direction, max_depth },
      }),
  },
  risk: {
    summary: (id: string) => apiRequest<RiskSummary>(`/repositories/${id}/risks/summary`),
    findings: (id: string, severity?: string) =>
      apiRequest<RiskFinding[]>(`/repositories/${id}/risks${query({ severity })}`),
    finding: (id: string, findingId: string) =>
      apiRequest<RiskFindingDetail>(`/repositories/${id}/risks/${findingId}`),
    analyze: (id: string) =>
      apiRequest<{ job_id: string; status: string }>(`/repositories/${id}/risks/analyze`, {
        method: "POST",
        body: { include_github_history: true, max_findings: 25 },
      }),
  },
  investigations: {
    list: (repositoryId: string) =>
      apiRequest<Page<Investigation>>(`/repositories/${repositoryId}/investigations`),
    create: (repositoryId: string, question: string, scope_path?: string) =>
      apiRequest<Investigation>(`/repositories/${repositoryId}/investigations`, {
        method: "POST",
        body: { question, scope_path: scope_path || null },
      }),
    get: (id: string) => apiRequest<InvestigationDetail>(`/investigations/${id}`),
    cancel: (id: string) =>
      apiRequest<InvestigationDetail>(`/investigations/${id}/cancel`, { method: "POST" }),
    evidence: (id: string) => apiRequest<Record<string, unknown>>(`/investigations/${id}/evidence`),
  },
  agents: {
    list: () => apiRequest<AgentDefinition[]>("/agents"),
    runs: (repositoryId?: string) =>
      apiRequest<AgentRunGlobal[]>(`/agents/runs${query({ repository_id: repositoryId })}`),
    stats: () =>
      apiRequest<{ agent_name: string; status: string; count: number; avg_execution_time: number }[]>(
        "/agents/stats",
      ),
  },
  reports: {
    list: (repositoryId: string) =>
      apiRequest<Page<Report>>(`/repositories/${repositoryId}/reports`),
    create: (repositoryId: string, title?: string, investigationId?: string) =>
      apiRequest<ReportDetail>(`/repositories/${repositoryId}/reports`, {
        method: "POST",
        body: { title: title || null, investigation_id: investigationId || null },
      }),
    get: (id: string) => apiRequest<ReportDetail>(`/reports/${id}`),
    export: (id: string) => `${API_BASE}/reports/${id}/export`,
  },
};

/** Probe helper retained for the system-status component and its tests. */
export interface EndpointResult {
  path: string;
  ok: boolean;
  httpStatus: number | null;
  latencyMs: number;
  requestId: string | null;
  body: unknown;
  failure: string | null;
}

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
