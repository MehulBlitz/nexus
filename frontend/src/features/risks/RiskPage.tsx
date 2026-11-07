import { AlertTriangle, ArrowUpRight, Loader2, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useFindings, useRiskAnalyze, useRiskSummary } from "@/hooks/queries";
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  Loading,
  Stat,
  formatDate,
  severityTone,
} from "@/components/ui";
import type { RiskFindingDetail, RiskSignal } from "@/types/api";

const severities = ["critical", "high", "moderate", "low"] as const;
const colors: Record<string, string> = {
  critical: "#f2777a",
  high: "#ef9f76",
  moderate: "#e8c468",
  low: "#5fd39a",
};

export function RiskPage() {
  const { repositoryId } = useParams();
  const summary = useRiskSummary(repositoryId);
  const [severity, setSeverity] = useState<string | undefined>(undefined);
  const findings = useFindings(repositoryId, severity);
  const analyze = useRiskAnalyze(repositoryId!);
  const [jobId, setJobId] = useState<string | null>(null);
  const client = useQueryClient();

  const job = useQuery({
    queryKey: ["risk-job", jobId],
    queryFn: () => api.jobs(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) =>
      query.state.data && ["QUEUED", "RUNNING"].includes(query.state.data.status) ? 1500 : false,
  });

  useEffect(() => {
    if (job.data && ["COMPLETED", "FAILED"].includes(job.data.status)) {
      void client.invalidateQueries({ queryKey: ["repository", repositoryId, "risk"] });
      setJobId(null);
    }
  }, [job.data, client, repositoryId]);

  if (summary.isLoading) return <Loading label="Loading risk analysis…" />;
  if (summary.isError) return <ErrorState message={summary.error.message} retry={() => void summary.refetch()} />;
  const data = summary.data!;
  const hasRun = Boolean(data.analysis_run_id);
  const distribution = severities.map((item) => ({ severity: item, count: data.severity_counts[item] ?? 0 }));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Risk center</h2>
          <p className="text-sm text-muted">
            Weighted heuristics over measured signals. This is a prioritisation score, not a
            probability of failure.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {job.data && ["QUEUED", "RUNNING"].includes(job.data.status) ? (
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <Loader2 className="size-3.5 animate-spin" aria-hidden /> analyzing ({job.data.progress}%)
            </span>
          ) : null}
          <Button
            onClick={() => {
              analyze.mutate(undefined, {
                onSuccess: (result) => setJobId(result.job_id),
              });
            }}
            disabled={analyze.isPending || Boolean(jobId)}
          >
            <ShieldAlert className="size-4" aria-hidden /> {hasRun ? "Re-run analysis" : "Run analysis"}
          </Button>
        </div>
      </div>

      {analyze.isError ? <ErrorState message={analyze.error.message} /> : null}
      {job.data?.status === "FAILED" ? (
        <ErrorState message={job.data.error_message ?? "Risk analysis failed"} />
      ) : null}

      {!hasRun ? (
        <EmptyState icon={ShieldAlert} title="No risk analysis for this snapshot">
          NEXUS can score modules using centrality, complexity, change frequency, test presence and
          recent activity. Run the analysis to create the first evidence-backed findings.
        </EmptyState>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              label="Overall score"
              value={data.overall_score != null ? data.overall_score.toFixed(1) : "—"}
              hint={data.overall_severity ? `${data.overall_severity} · ${data.module_count} modules` : undefined}
              icon={ShieldAlert}
            />
            <Stat label="Analysis confidence" value={`${(data.confidence * 100).toFixed(0)}%`} hint={`${data.signals_available.length} of 5 signals available`} />
            <Stat label="Findings" value={findings.data?.length ?? 0} hint="Findings at or above the moderate threshold" />
            <Stat label="Analyzed" value={formatDate(data.analyzed_at)} hint="Snapshot-scoped analysis" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Card>
              <CardTitle>Severity breakdown</CardTitle>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={distribution} layout="vertical" margin={{ left: 8, right: 12 }}>
                    <CartesianGrid horizontal={false} stroke="#262b37" />
                    <XAxis type="number" allowDecimals={false} tick={{ fill: "#8d95a8", fontSize: 11 }} />
                    <YAxis type="category" dataKey="severity" width={70} tick={{ fill: "#8d95a8", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "#151820", border: "1px solid #262b37", fontSize: 12 }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {distribution.map((item) => (
                        <Cell key={item.severity} fill={colors[item.severity]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card>
              <CardTitle>Signals</CardTitle>
              <div className="space-y-2">
                {Object.entries(data.weights).map(([name, weight]) => {
                  const available = data.signals_available.includes(name);
                  return (
                    <div key={name} className="flex items-center justify-between gap-2 text-sm">
                      <span className="capitalize">{name.replaceAll("_", " ")}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted">weight {(weight * 100).toFixed(0)}%</span>
                        <Badge tone={available ? "ok" : "warn"}>{available ? "available" : "excluded"}</Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
              {data.limitations.length > 0 ? (
                <ul className="mt-4 space-y-1 border-t border-line pt-3 text-xs text-muted">
                  {data.limitations.map((limitation) => (
                    <li key={limitation}>· {limitation}</li>
                  ))}
                </ul>
              ) : null}
            </Card>
          </div>

          {data.classified_modules.length > 0 ? (
            <Card>
              <CardTitle>Highest-risk modules</CardTitle>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wider text-muted">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Module</th>
                      <th className="px-3 py-2 font-medium">Score</th>
                      <th className="px-3 py-2 font-medium">Severity</th>
                      <th className="px-3 py-2 font-medium">Confidence</th>
                      <th className="px-3 py-2 font-medium">Signals used</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data.classified_modules.slice(0, 12).map((module) => (
                      <tr key={module.path}>
                        <td className="max-w-md truncate py-2 pr-3 font-mono text-xs">{module.path}</td>
                        <td className="px-3 py-2 tabular-nums">{module.score.toFixed(1)}</td>
                        <td className="px-3 py-2">
                          <Badge tone={severityTone(module.severity)}>{module.severity}</Badge>
                        </td>
                        <td className="px-3 py-2 tabular-nums text-muted">{(module.confidence * 100).toFixed(0)}%</td>
                        <td className="px-3 py-2 text-xs text-muted">{module.used_signals.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : null}
        </>
      )}

      <Card>
        <CardTitle
          action={
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                onClick={() => setSeverity(undefined)}
                className={`rounded px-2 py-0.5 text-xs ${!severity ? "bg-accent/15 text-accent" : "text-muted hover:text-text"}`}
              >
                all
              </button>
              {severities.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setSeverity(item)}
                  className={`rounded px-2 py-0.5 text-xs ${severity === item ? "bg-accent/15 text-accent" : "text-muted hover:text-text"}`}
                >
                  {item}
                </button>
              ))}
            </div>
          }
        >
          Findings
        </CardTitle>
        {findings.isLoading ? (
          <Loading label="Loading findings…" />
        ) : findings.isError ? (
          <ErrorState message={findings.error.message} />
        ) : (findings.data?.length ?? 0) === 0 ? (
          <EmptyState icon={ShieldAlert} title={hasRun ? "No findings at this threshold" : "Run an analysis first"}>
            {hasRun
              ? "The weighted score did not cross the moderate threshold for any module. Missing signals are excluded rather than invented."
              : undefined}
          </EmptyState>
        ) : (
          <ul className="space-y-2">
            {findings.data!.map((finding) => (
              <li key={finding.id}>
                <FindingRow finding={finding} repositoryId={repositoryId!} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function FindingRow({
  finding,
  repositoryId,
}: {
  finding: { id: string; title: string; severity: string; risk_score: number; confidence: number; file_path: string | null; description: string; origin: string };
  repositoryId: string;
}) {
  const [open, setOpen] = useState(false);
  const detail = useQuery({
    queryKey: ["risk-finding", repositoryId, finding.id],
    queryFn: () => api.risk.finding(repositoryId, finding.id),
    enabled: open,
  });

  return (
    <div className="rounded-lg border border-line">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start justify-between gap-3 p-3 text-left"
        aria-expanded={open}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
            <span className="text-sm font-medium">{finding.title}</span>
            <Badge tone="neutral">{finding.origin}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">
            {finding.file_path ?? "repository-wide"} · score {finding.risk_score.toFixed(1)} · confidence{" "}
            {(finding.confidence * 100).toFixed(0)}%
          </p>
        </div>
        <ArrowUpRight className={`mt-1 size-4 shrink-0 text-muted transition ${open ? "rotate-90" : ""}`} aria-hidden />
      </button>
      {open ? (
        <div className="border-t border-line p-3 text-sm">
          {detail.isLoading ? (
            <Loading label="Loading evidence…" />
          ) : detail.isError ? (
            <ErrorState message={detail.error.message} />
          ) : detail.data ? (
            <FindingDetail finding={detail.data} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function FindingDetail({ finding }: { finding: RiskFindingDetail }) {
  const evidence = finding.evidence_json ?? {};
  return (
    <div className="space-y-3">
      <p className="text-muted">{finding.description}</p>
      <div>
        <p className="text-xs uppercase tracking-wider text-muted">Signals</p>
        {finding.signals.length === 0 ? (
          <p className="text-xs text-muted">No per-signal breakdown stored for this finding.</p>
        ) : (
          <ul className="mt-1 space-y-1.5">
            {finding.signals.map((signal) => (
              <SignalBar key={signal.name} signal={signal} />
            ))}
          </ul>
        )}
      </div>
      {Array.isArray(finding.recommendations_json) && finding.recommendations_json.length > 0 ? (
        <div>
          <p className="text-xs uppercase tracking-wider text-muted">Recommended next steps</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-muted">
            {finding.recommendations_json.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {Object.keys(evidence).length > 0 ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted hover:text-text">Raw evidence</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-ink/70 p-2 text-[11px] text-muted">
            {JSON.stringify(evidence, null, 2)}
          </pre>
        </details>
      ) : (
        <p className="flex items-center gap-1 text-xs text-warn">
          <AlertTriangle className="size-3" aria-hidden /> No structured evidence stored; treat this
          finding as unsupported.
        </p>
      )}
    </div>
  );
}

function SignalBar({ signal }: { signal: RiskSignal }) {
  return (
    <li>
      <div className="flex items-center justify-between text-xs">
        <span className="capitalize">{signal.name.replaceAll("_", " ")}</span>
        <span className="text-muted">
          {signal.available && signal.normalized != null ? `${signal.normalized.toFixed(0)}/100` : "unavailable"}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-line">
        <div
          className="h-full bg-accent"
          style={{ width: `${signal.available && signal.normalized != null ? signal.normalized : 0}%` }}
        />
      </div>
      <p className="mt-0.5 text-[11px] text-muted">{signal.explanation}</p>
    </li>
  );
}
