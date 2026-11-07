import {
  Activity,
  ArrowRight,
  Boxes,
  FileCode2,
  GitPullRequest,
  Plus,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useDashboard } from "@/hooks/queries";
import { Badge, Card, CardTitle, EmptyState, ErrorState, Loading, Stat, formatDate, relativeTime, severityTone } from "@/components/ui";

const severityOrder = ["critical", "high", "moderate", "low"] as const;
const severityColors: Record<string, string> = {
  critical: "#f2777a",
  high: "#ef9f76",
  moderate: "#e8c468",
  low: "#5fd39a",
};

export function DashboardPage() {
  const dashboard = useDashboard();

  if (dashboard.isLoading) return <Loading label="Loading workspace…" />;
  if (dashboard.isError) {
    return <ErrorState message={dashboard.error.message} retry={() => void dashboard.refetch()} />;
  }
  const data = dashboard.data!;
  const distribution = severityOrder.map((severity) => ({
    severity,
    count: data.risk_distribution[severity] ?? 0,
  }));
  const hasRisk = distribution.some((item) => item.count > 0);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Engineering intelligence</h1>
          <p className="mt-1 text-sm text-muted">
            Everything below is computed from repositories you imported and indexed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={data.ai_configured ? "accent" : "neutral"}>
            <Sparkles className="size-3" aria-hidden />
            AI {data.ai_configured ? data.ai_provider : "deterministic fallback"}
          </Badge>
          <Link
            to="/app/repositories"
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-ink"
          >
            <Plus className="size-4" aria-hidden /> Import repository
          </Link>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Repositories" value={data.repository_count} icon={Boxes} hint={`${data.indexed_file_count} indexed files`} />
        <Stat label="Symbols" value={data.symbol_count} icon={FileCode2} hint="Functions, classes and modules" />
        <Stat
          label="Open investigations"
          value={data.open_investigation_count}
          icon={Activity}
          hint={`${data.completed_investigation_count} completed`}
        />
        <Stat label="Active jobs" value={data.active_job_count} icon={GitPullRequest} hint={`${data.report_count} reports generated`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardTitle
            action={
              <Link to="/app/repositories" className="text-xs text-accent hover:underline">
                All repositories
              </Link>
            }
          >
            Repositories
          </CardTitle>
          {data.repositories.length === 0 ? (
            <EmptyState icon={Boxes} title="No repositories yet" action={<Link to="/app/repositories" className="text-sm text-accent hover:underline">Import a public GitHub repository</Link>}>
              NEXUS needs a repository before it can build a graph, score risk or investigate a
              problem.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {data.repositories.slice(0, 6).map((repo) => (
                <li key={repo.id}>
                  <Link
                    to={`/app/repositories/${repo.id}`}
                    className="flex items-center justify-between gap-3 py-3 transition hover:bg-white/[0.02]"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{repo.full_name}</p>
                      <p className="mt-0.5 truncate text-xs text-muted">
                        {repo.description || "No description"} · indexed {relativeTime(repo.last_indexed_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {repo.language ? <span className="hidden text-xs text-muted sm:inline">{repo.language}</span> : null}
                      <Badge tone={repo.status === "indexed" ? "ok" : repo.status === "failed" ? "fail" : "warn"}>
                        {repo.status}
                      </Badge>
                      <ArrowRight className="size-3.5 text-muted" aria-hidden />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardTitle>Risk distribution</CardTitle>
          {!hasRisk ? (
            <EmptyState icon={ShieldAlert} title="No risk analysis yet">
              Run an analysis inside a repository to populate severity counts and evidence-backed
              findings.
            </EmptyState>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distribution} layout="vertical" margin={{ left: 8, right: 12 }}>
                  <CartesianGrid horizontal={false} stroke="#262b37" />
                  <XAxis type="number" allowDecimals={false} tick={{ fill: "#8d95a8", fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="severity"
                    width={68}
                    tick={{ fill: "#8d95a8", fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ background: "#151820", border: "1px solid #262b37", fontSize: 12 }}
                    labelStyle={{ color: "#e7e9ef" }}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {distribution.map((item) => (
                      <Cell key={item.severity} fill={severityColors[item.severity]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {severityOrder.map((severity) => (
              <Badge key={severity} tone={severityTone(severity)}>
                {severity}: {data.risk_distribution[severity] ?? 0}
              </Badge>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardTitle>Recent activity</CardTitle>
          {data.recent_activity.length === 0 ? (
            <EmptyState icon={Activity} title="No activity recorded yet">
              Imports, indexing runs, investigations and reports are written to the audit trail.
            </EmptyState>
          ) : (
            <ul className="space-y-2.5">
              {data.recent_activity.map((event) => (
                <li key={event.id} className="flex items-start justify-between gap-3 text-sm">
                  <div>
                    <p className="font-medium">{event.action.replaceAll("_", " ")}</p>
                    <p className="text-xs text-muted">
                      {event.resource_type}
                      {event.resource_id ? ` · ${event.resource_id.slice(0, 8)}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-muted">{relativeTime(event.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardTitle
            action={
              <Link to="/app/agents" className="text-xs text-accent hover:underline">
                Agent center
              </Link>
            }
          >
            Agent activity
          </CardTitle>
          {data.agent_activity.length === 0 ? (
            <EmptyState icon={Sparkles} title="No agent runs yet">
              Start an investigation to see the mapper, investigator, risk analyst, architecture
              reviewer and planner execute.
            </EmptyState>
          ) : (
            <ul className="space-y-2.5">
              {data.agent_activity.map((run) => (
                <li key={run.id} className="flex items-center justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{run.agent_name.replaceAll("_", " ")}</p>
                    <p className="text-xs text-muted">
                      {run.execution_time != null ? `${run.execution_time.toFixed(2)}s` : "—"} ·{" "}
                      {formatDate(run.started_at)}
                    </p>
                  </div>
                  <Badge tone={run.status === "completed" ? "ok" : run.status === "failed" ? "fail" : "warn"}>
                    {run.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
