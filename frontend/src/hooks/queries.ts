import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardStats, RepositoryStatusResponse } from "@/types/api";

export const queryKeys = {
  me: ["me"] as const,
  dashboard: ["dashboard"] as const,
  repositories: ["repositories"] as const,
  repository: (id: string) => ["repository", id] as const,
  repositoryStatus: (id: string) => ["repository", id, "status"] as const,
  overview: (id: string) => ["repository", id, "overview"] as const,
  activity: (id: string) => ["repository", id, "activity"] as const,
  files: (id: string) => ["repository", id, "files"] as const,
  symbols: (id: string, q: string) => ["repository", id, "symbols", q] as const,
  search: (id: string, q: string) => ["repository", id, "search", q] as const,
  graph: (id: string) => ["repository", id, "graph"] as const,
  graphMetrics: (id: string) => ["repository", id, "graph", "metrics"] as const,
  riskSummary: (id: string) => ["repository", id, "risk", "summary"] as const,
  findings: (id: string) => ["repository", id, "risk", "findings"] as const,
  investigations: (id: string) => ["repository", id, "investigations"] as const,
  investigation: (id: string) => ["investigation", id] as const,
  reports: (id: string) => ["repository", id, "reports"] as const,
  report: (id: string) => ["report", id] as const,
  agents: ["agents"] as const,
  agentRuns: (id?: string) => ["agents", "runs", id ?? "all"] as const,
  agentStats: ["agents", "stats"] as const,
  tokens: ["tokens"] as const,
};

export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: api.auth.me,
    retry: false,
    staleTime: 60_000,
  });
}

export function useDashboard() {
  return useQuery<DashboardStats>({ queryKey: queryKeys.dashboard, queryFn: api.dashboard });
}

export function useRepositories() {
  return useQuery({ queryKey: queryKeys.repositories, queryFn: () => api.repositories.list() });
}

export function useRepository(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.repository(id ?? ""),
    queryFn: () => api.repositories.get(id!),
    enabled: Boolean(id),
  });
}

export function useRepositoryStatus(id: string | undefined, poll: boolean) {
  return useQuery<RepositoryStatusResponse>({
    queryKey: queryKeys.repositoryStatus(id ?? ""),
    queryFn: () => api.repositories.status(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!poll) return false;
      if (!data) return 1500;
      const active = data.active_job && ["QUEUED", "RUNNING"].includes(data.active_job.status);
      return active ? 1500 : false;
    },
  });
}

export function useOverview(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.overview(id ?? ""),
    queryFn: () => api.repositories.overview(id!),
    enabled: Boolean(id),
  });
}

export function useActivity(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.activity(id ?? ""),
    queryFn: () => api.repositories.activity(id!),
    enabled: Boolean(id),
    staleTime: 60_000,
  });
}

export function useFiles(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.files(id ?? ""),
    queryFn: () => api.repositories.files(id!, 200, 0),
    enabled: Boolean(id),
  });
}

export function useSymbolSearch(id: string | undefined, q: string) {
  return useQuery({
    queryKey: queryKeys.symbols(id ?? "", q),
    queryFn: () => api.repositories.symbols(id!, q || undefined, undefined, 50),
    enabled: Boolean(id),
  });
}

export function useCodeSearch(id: string | undefined, q: string) {
  return useQuery({
    queryKey: queryKeys.search(id ?? "", q),
    queryFn: () => api.repositories.search(id!, q),
    enabled: Boolean(id) && q.trim().length >= 2,
  });
}

export function useGraph(id: string | undefined, filters: { nodeTypes?: string; search?: string }) {
  return useQuery({
    queryKey: [...queryKeys.graph(id ?? ""), filters.nodeTypes ?? "", filters.search ?? ""],
    queryFn: () =>
      api.graph.view(id!, {
        node_types: filters.nodeTypes,
        search: filters.search || undefined,
        limit: 250,
      }),
    enabled: Boolean(id),
  });
}

export function useGraphMetrics(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.graphMetrics(id ?? ""),
    queryFn: () => api.graph.metrics(id!),
    enabled: Boolean(id),
  });
}

export function useRiskSummary(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.riskSummary(id ?? ""),
    queryFn: () => api.risk.summary(id!),
    enabled: Boolean(id),
  });
}

export function useFindings(id: string | undefined, severity?: string) {
  return useQuery({
    queryKey: [...queryKeys.findings(id ?? ""), severity ?? "all"],
    queryFn: () => api.risk.findings(id!, severity),
    enabled: Boolean(id),
  });
}

export function useRiskAnalyze(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.risk.analyze(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.riskSummary(id) });
      void client.invalidateQueries({ queryKey: queryKeys.findings(id) });
    },
  });
}

export function useInvestigations(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.investigations(id ?? ""),
    queryFn: () => api.investigations.list(id!),
    enabled: Boolean(id),
  });
}

export function useInvestigation(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.investigation(id ?? ""),
    queryFn: () => api.investigations.get(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      return ["queued", "running"].includes(data.status) ? 1500 : false;
    },
  });
}

export function useCreateInvestigation(repositoryId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { question: string; scope_path?: string }) =>
      api.investigations.create(repositoryId, input.question, input.scope_path),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.investigations(repositoryId) });
    },
  });
}

export function useReports(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.reports(id ?? ""),
    queryFn: () => api.reports.list(id!),
    enabled: Boolean(id),
  });
}

export function useReport(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.report(id ?? ""),
    queryFn: () => api.reports.get(id!),
    enabled: Boolean(id),
  });
}

export function useCreateReport(repositoryId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { title?: string; investigationId?: string }) =>
      api.reports.create(repositoryId, input.title, input.investigationId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.reports(repositoryId) });
    },
  });
}

export function useAgents() {
  return useQuery({ queryKey: queryKeys.agents, queryFn: api.agents.list, staleTime: 300_000 });
}

export function useAgentRuns(repositoryId?: string) {
  return useQuery({
    queryKey: queryKeys.agentRuns(repositoryId),
    queryFn: () => api.agents.runs(repositoryId),
    refetchInterval: 5000,
  });
}

export function useAgentStats() {
  return useQuery({ queryKey: queryKeys.agentStats, queryFn: api.agents.stats });
}

export function useApiTokens(enabled: boolean) {
  return useQuery({ queryKey: queryKeys.tokens, queryFn: api.auth.tokens, enabled });
}
