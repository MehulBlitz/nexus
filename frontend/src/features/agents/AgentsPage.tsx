import { Activity, Bot, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useAgentRuns, useAgentStats, useAgents } from "@/hooks/queries";
import { Badge, Card, CardTitle, EmptyState, ErrorState, Loading, formatDate, relativeTime } from "@/components/ui";

export function AgentsPage() {
  const agents = useAgents();
  const stats = useAgentStats();
  const runs = useAgentRuns();

  if (agents.isLoading) return <Loading label="Loading agents…" />;
  if (agents.isError) return <ErrorState message={agents.error.message} retry={() => void agents.refetch()} />;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Agent center</h1>
        <p className="mt-1 text-sm text-muted">
          Five specialised roles with distinct output contracts. The orchestrator validates every
          result and records failures instead of inventing replacements.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.data!.map((agent) => (
          <Card key={agent.name}>
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="grid size-8 place-items-center rounded-lg bg-accent/10 text-accent">
                  <Bot className="size-4" aria-hidden />
                </span>
                <h2 className="font-medium">{agent.title}</h2>
              </div>
              <Badge tone={agent.uses_llm_when_available ? "accent" : "neutral"}>
                {agent.uses_llm_when_available ? "LLM optional" : "deterministic"}
              </Badge>
            </div>
            <p className="mt-3 text-sm text-muted">{agent.responsibility}</p>
            <p className="mt-3 font-mono text-[11px] text-muted">output: {agent.output_schema}</p>
            <p className="mt-1 font-mono text-[11px] text-muted">name: {agent.name}</p>
          </Card>
        ))}
      </div>

      <Card>
        <CardTitle>Execution statistics</CardTitle>
        {stats.isLoading ? (
          <Loading label="Loading statistics…" />
        ) : stats.isError ? (
          <ErrorState message={stats.error.message} />
        ) : (stats.data?.length ?? 0) === 0 ? (
          <EmptyState icon={Activity} title="No runs recorded yet">
            Statistics appear after the first investigation.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="py-2 pr-3 font-medium">Agent</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 text-right font-medium">Runs</th>
                  <th className="px-3 py-2 text-right font-medium">Avg time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {stats.data!.map((row) => (
                  <tr key={`${row.agent_name}-${row.status}`}>
                    <td className="py-2 pr-3 capitalize">{row.agent_name.replaceAll("_", " ")}</td>
                    <td className="px-3 py-2">
                      <Badge tone={row.status === "completed" ? "ok" : row.status === "failed" ? "fail" : "warn"}>{row.status}</Badge>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.count}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted">
                      {row.avg_execution_time != null ? `${row.avg_execution_time.toFixed(2)}s` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Recent agent runs</CardTitle>
        {runs.isLoading ? (
          <Loading label="Loading runs…" />
        ) : runs.isError ? (
          <ErrorState message={runs.error.message} />
        ) : (runs.data?.length ?? 0) === 0 ? (
          <EmptyState icon={Sparkles} title="No agent runs yet">
            Start an investigation inside a repository to populate the execution history.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="py-2 pr-3 font-medium">Agent</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Investigation</th>
                  <th className="px-3 py-2 text-right font-medium">Time</th>
                  <th className="px-3 py-2 text-right font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {runs.data!.slice(0, 40).map((run) => (
                  <tr key={run.id}>
                    <td className="py-2 pr-3 capitalize">{run.agent_name.replaceAll("_", " ")}</td>
                    <td className="px-3 py-2">
                      <Badge tone={run.status === "completed" ? "ok" : run.status === "failed" ? "fail" : "warn"}>{run.status}</Badge>
                    </td>
                    <td className="max-w-xs truncate px-3 py-2 text-xs">
                      <Link
                        to={`/app/repositories/${run.repository_id}/investigations/${run.investigation_id}`}
                        className="text-accent hover:underline"
                      >
                        {run.question ?? run.investigation_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted">
                      {run.execution_time != null ? `${run.execution_time.toFixed(2)}s` : "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-xs text-muted" title={formatDate(run.started_at)}>
                      {relativeTime(run.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
