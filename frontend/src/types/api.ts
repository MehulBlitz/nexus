export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  csrf_token: string;
  expires_at: string;
}

export interface Repository {
  id: string;
  provider: string;
  external_repository_id: string;
  name: string;
  full_name: string;
  html_url: string;
  description: string | null;
  default_branch: string;
  visibility: string;
  status: RepositoryStatus;
  language: string | null;
  stars: number;
  size_kb: number;
  last_indexed_at: string | null;
  last_error: string | null;
  created_at: string;
}

export type RepositoryStatus = "pending" | "queued" | "indexing" | "indexed" | "failed";

export interface Snapshot {
  id: string;
  commit_sha: string;
  branch: string;
  indexing_status: string;
  file_count: number;
  symbol_count: number;
  edge_count: number;
  languages: Record<string, number> | null;
  warnings: string[] | null;
  coverage: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
}

export interface Job {
  id: string;
  job_type: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress: number;
  repository_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface RepositoryDetail extends Repository {
  latest_snapshot: Snapshot | null;
  active_job: Job | null;
}

export interface RepositoryStatusResponse {
  repository_id: string;
  status: RepositoryStatus;
  active_job: Job | null;
  latest_snapshot: Snapshot | null;
  last_error: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface LanguageStat {
  language: string;
  files: number;
  symbols: number;
  percent: number;
}

export interface RepositoryOverview {
  repository: Repository;
  snapshot: Snapshot | null;
  languages: LanguageStat[];
  file_count: number;
  symbol_count: number;
  module_count: number;
  test_file_count: number;
  top_modules: { path: string; degree_centrality: number }[];
  directories: { name: string; files: number }[];
  entry_points: string[];
  parser_coverage: {
    parse_modes?: Record<string, number>;
    skipped_reasons?: Record<string, number>;
    fetch_failures?: number;
    analyzer_note?: string;
  };
  warnings: string[];
}

export interface FileEntry {
  path: string;
  language: string;
  node_id: string;
  line_count: number | null;
  symbols: number;
  imports: number;
}

export interface SymbolEntry {
  id: string;
  name: string;
  qualified_name: string | null;
  node_type: string;
  file_path: string | null;
  start_line: number | null;
  end_line: number | null;
  language: string | null;
}

export interface SearchHit {
  path: string;
  language: string;
  line: number;
  match_type: "path" | "symbol" | "content";
  snippet: string;
  symbol: string | null;
}

export interface ActivitySection {
  available: boolean;
  reason: string | null;
  fetched_at: string | null;
  items: Record<string, unknown>[];
}

export interface RepositoryActivity {
  repository_id: string;
  full_name: string;
  commits: ActivitySection;
  pull_requests: ActivitySection;
  issues: ActivitySection;
  workflows: ActivitySection;
  summary: string;
}

export interface GraphNode {
  id: string;
  node_type: string;
  name: string;
  qualified_name: string | null;
  file_path: string | null;
  start_line: number | null;
  end_line: number | null;
  language: string | null;
  in_degree: number;
  out_degree: number;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
  origin: string;
  detail: string | null;
  evidence: Record<string, unknown> | null;
}

export interface GraphResponse {
  snapshot_id: string | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  node_total: number;
  edge_total: number;
  filters: Record<string, unknown>;
}

export interface GraphMetrics {
  node_count: number;
  edge_count: number;
  cycle_count: number;
  weakly_connected_components: number;
  top_central: { path: string; degree_centrality: number }[];
  missing_evidence_edges: number;
}

export interface DependencyChain {
  root: GraphNode;
  direction: "dependencies" | "dependents";
  max_depth: number;
  steps: {
    node: GraphNode;
    depth: number;
    via_edge: GraphEdge | null;
    path: string[];
    relationship?: string | null;
  }[];
  truncated: boolean;
  explanation: string;
}

export interface ImpactResult {
  root: GraphNode;
  direction: string;
  max_depth: number;
  affected: {
    node: GraphNode;
    depth: number;
    path: string[];
    relationship: string;
  }[];
  related_tests: GraphNode[];
  depths_reached: number;
  truncated: boolean;
  explanation: string;
  evidence: Record<string, unknown>[];
}

export interface RiskSignal {
  name: string;
  weight: number;
  value: number | null;
  normalized: number | null;
  available: boolean;
  explanation: string;
}

export interface RiskFinding {
  id: string;
  analysis_run_id: string;
  repository_id: string;
  snapshot_id: string | null;
  finding_type: string;
  severity: "low" | "moderate" | "high" | "critical";
  title: string;
  description: string;
  risk_score: number;
  confidence: number;
  origin: string;
  file_path: string | null;
  evidence_json: Record<string, unknown> | null;
  recommendations_json: string[] | null;
  created_at: string;
}

export interface RiskFindingDetail extends RiskFinding {
  signals: RiskSignal[];
}

export interface RiskSummary {
  repository_id: string;
  snapshot_id: string | null;
  analysis_run_id: string | null;
  overall_score: number | null;
  overall_severity: string | null;
  analyzed_at: string | null;
  module_count: number;
  severity_counts: Record<string, number>;
  signals_available: string[];
  signals_unavailable: string[];
  weights: Record<string, number>;
  classified_modules: {
    path: string;
    score: number;
    severity: string;
    confidence: number;
    used_signals: string[];
  }[];
  confidence: number;
  limitations: string[];
}

export interface Investigation {
  id: string;
  repository_id: string;
  job_id?: string | null;
  question: string;
  scope_path: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  summary: string | null;
  ai_used: boolean;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface EvidenceRef {
  file: string;
  start_line: number | null;
  end_line: number | null;
  note?: string | null;
  origin?: string;
}

export interface Hypothesis {
  title: string;
  confidence: number;
  reasoning: string;
  evidence: EvidenceRef[];
  origin: string;
  suggested_check?: string | null;
}

export interface PlanItem {
  priority: "P0" | "P1" | "P2" | "P3";
  problem: string;
  evidence: EvidenceRef[];
  suggested_fix: string;
  related_files: string[];
  suggested_tests: string[];
  dependencies: string[];
  complexity: string;
  requires_human_approval: boolean;
}

export interface AgentRun {
  id: string;
  agent_name: string;
  status: string;
  output_json: Record<string, unknown> | null;
  execution_time: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface InvestigationDetail extends Investigation {
  result: {
    summary?: string;
    hypotheses?: Hypothesis[];
    recommended_actions?: string[];
    agents?: Record<string, Record<string, unknown>>;
    plan?: PlanItem[];
    limitations?: string[];
    ai?: { used: boolean; provider: string; note: string };
    evidence_verification?: { files_checked: number; issues: string[] };
    agent_status?: { agent: string; status: string; execution_time: number; error: string | null }[];
  } | null;
  agent_runs: AgentRun[];
}

export interface AgentDefinition {
  name: string;
  title: string;
  responsibility: string;
  uses_llm_when_available: boolean;
  output_schema: string;
}

export interface AgentRunGlobal extends Omit<AgentRun, "output_json"> {
  investigation_id: string;
  repository_id: string;
  question: string | null;
}

export interface Report {
  id: string;
  repository_id: string;
  title: string;
  snapshot_id: string | null;
  created_at: string;
}

export interface ReportDetail extends Report {
  markdown: string;
}

export interface DashboardStats {
  repository_count: number;
  indexed_file_count: number;
  symbol_count: number;
  active_job_count: number;
  open_investigation_count: number;
  completed_investigation_count: number;
  report_count: number;
  risk_distribution: Record<string, number>;
  repositories: Repository[];
  recent_activity: {
    id: string;
    action: string;
    resource_type: string;
    resource_id: string | null;
    created_at: string;
  }[];
  agent_activity: {
    id: string;
    agent_name: string;
    status: string;
    execution_time: number | null;
    started_at: string | null;
    investigation_id: string;
  }[];
  ai_configured: boolean;
  ai_provider: string;
}

export interface ApiToken {
  id: string;
  name: string;
  prefix: string;
  scope: string;
  created_at: string;
  last_used_at: string | null;
}
