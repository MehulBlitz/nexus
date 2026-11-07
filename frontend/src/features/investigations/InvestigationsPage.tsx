import { Activity, ArrowLeft, Loader2, Sparkles, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";
import { useCreateInvestigation, useInvestigation, useInvestigations } from "@/hooks/queries";
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  formatDate,
  inputClass,
  relativeTime,
} from "@/components/ui";
import type { Hypothesis, PlanItem } from "@/types/api";

const questionSchema = z.object({
  question: z.string().trim().min(8, "Ask a question with at least 8 characters").max(2000),
  scope_path: z.string().trim().max(500).optional(),
});

export function InvestigationsPage() {
  const { repositoryId } = useParams();
  const investigations = useInvestigations(repositoryId);
  const create = useCreateInvestigation(repositoryId!);
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = questionSchema.safeParse({ question, scope_path: scope });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) next[String(issue.path[0])] = issue.message;
      setErrors(next);
      return;
    }
    setErrors({});
    create.mutate(
      { question: parsed.data.question, scope_path: parsed.data.scope_path },
      {
        onSuccess: (investigation) => {
          setQuestion("");
          setScope("");
          navigate(`investigations/${investigation.id}`);
        },
      },
    );
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardTitle>Start an investigation</CardTitle>
        <form onSubmit={submit} className="space-y-3" noValidate>
          <Field
            label="Question"
            htmlFor="question"
            error={errors.question}
            hint="Describe the problem. Every source claim must resolve to a file and line range."
          >
            <textarea
              id="question"
              rows={3}
              className={inputClass}
              placeholder="Why might the session refresh path lose authentication state?"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              aria-invalid={Boolean(errors.question)}
            />
          </Field>
          <Field label="Scope (optional)" htmlFor="scope" error={errors.scope_path} hint="Limit context to a directory or file path">
            <input
              id="scope"
              className={inputClass}
              placeholder="app/auth"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            />
          </Field>
          {create.isError ? <ErrorState message={create.error.message} /> : null}
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            Investigate
          </Button>
        </form>
        <p className="mt-3 text-xs text-muted">
          Agents run in parallel against the indexed snapshot. The LLM is optional; without one, the
          deterministic evidence-backed analysis still runs and the result says AI reasoning is
          unavailable.
        </p>
      </Card>

      <Card>
        <CardTitle>Investigation history</CardTitle>
        {investigations.isLoading ? (
          <Loading label="Loading investigations…" />
        ) : investigations.isError ? (
          <ErrorState message={investigations.error.message} />
        ) : (investigations.data?.items.length ?? 0) === 0 ? (
          <EmptyState icon={Activity} title="No investigations yet">
            Ask a question above to start the multi-agent workflow.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {investigations.data!.items.map((item) => (
              <li key={item.id}>
                <Link
                  to={`investigations/${item.id}`}
                  className="flex items-start justify-between gap-3 py-3 hover:bg-white/[0.02]"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.question}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {item.scope_path ? `${item.scope_path} · ` : ""}
                      {item.ai_used ? "AI-assisted" : "Deterministic"} · {relativeTime(item.created_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {["queued", "running"].includes(item.status) ? (
                      <span className="text-xs text-muted">{item.progress}%</span>
                    ) : null}
                    <Badge tone={item.status === "completed" ? "ok" : item.status === "failed" ? "fail" : "warn"}>
                      {item.status}
                    </Badge>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function InvestigationDetailPage() {
  const { repositoryId, investigationId } = useParams();
  const investigation = useInvestigation(investigationId);
  const client = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => api.investigations.cancel(investigationId!),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["investigation", investigationId] });
    },
  });

  if (investigation.isLoading) return <Loading label="Loading investigation…" />;
  if (investigation.isError) {
    return <ErrorState message={investigation.error.message} retry={() => void investigation.refetch()} />;
  }
  const item = investigation.data!;
  const result = item.result as InvestigationResultJson | null;
  const running = ["queued", "running"].includes(item.status);

  return (
    <div className="space-y-5">
      <Link to={`/app/repositories/${repositoryId}/investigations`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-text">
        <ArrowLeft className="size-3" aria-hidden /> All investigations
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">{item.question}</h2>
            <Badge tone={item.status === "completed" ? "ok" : item.status === "failed" ? "fail" : "warn"}>{item.status}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">
            {item.scope_path ? `Scope ${item.scope_path} · ` : ""}
            Started {formatDate(item.started_at ?? item.created_at)} ·{" "}
            {item.completed_at ? `completed ${formatDate(item.completed_at)}` : "in progress"} ·{" "}
            {item.ai_used ? "AI reasoning used" : "deterministic analysis"}
          </p>
        </div>
        {running ? (
          <Button variant="danger" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
            <XCircle className="size-4" aria-hidden /> Cancel
          </Button>
        ) : null}
      </div>

      {running ? (
        <div className="rounded-lg border border-line bg-surface/60 p-3">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Progress</span>
            <span>{item.progress}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
            <div className="h-full bg-accent transition-all" style={{ width: `${item.progress}%` }} />
          </div>
        </div>
      ) : null}
      {item.error_message ? (
        <p className="rounded-lg border border-fail/30 bg-fail/5 p-3 text-sm text-fail">{item.error_message}</p>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card>
            <CardTitle>Summary</CardTitle>
            {result?.summary ?? item.summary ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{result?.summary ?? item.summary}</p>
            ) : (
              <p className="text-sm text-muted">
                {running ? "Agents are still working…" : "No summary was produced."}
              </p>
            )}
            {result?.ai ? (
              <p className="mt-3 border-t border-line pt-3 text-xs text-muted">
                AI: {result.ai.used ? `${result.ai.provider} · used` : "not used"} — {result.ai.note}
              </p>
            ) : null}
            {result?.evidence_verification ? (
              <p className="mt-1 text-xs text-muted">
                Evidence check: {result.evidence_verification.files_checked} files checked,{" "}
                {result.evidence_verification.issues.length} issue(s).
              </p>
            ) : null}
          </Card>

          <Card>
            <CardTitle action={<Badge>{result?.hypotheses?.length ?? 0}</Badge>}>Hypotheses</CardTitle>
            {!result?.hypotheses?.length ? (
              <p className="text-sm text-muted">No hypotheses were produced.</p>
            ) : (
              <ul className="space-y-3">
                {result.hypotheses.map((hypothesis) => (
                  <HypothesisCard key={hypothesis.title} hypothesis={hypothesis} />
                ))}
              </ul>
            )}
          </Card>

          {result?.plan && result.plan.length > 0 ? (
            <Card>
              <CardTitle>Review plan</CardTitle>
              <ul className="space-y-3">
                {result.plan.map((planItem) => (
                  <PlanCard key={`${planItem.priority}-${planItem.problem}`} item={planItem} />
                ))}
              </ul>
            </Card>
          ) : null}

          {result?.recommended_actions && result.recommended_actions.length > 0 ? (
            <Card>
              <CardTitle>Recommended actions</CardTitle>
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
                {result.recommended_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </Card>
          ) : null}

          {result?.limitations && result.limitations.length > 0 ? (
            <Card>
              <CardTitle>Limitations</CardTitle>
              <ul className="space-y-1 text-sm text-muted">
                {result.limitations.map((limitation) => (
                  <li key={limitation}>· {limitation}</li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardTitle>Agent timeline</CardTitle>
            {item.agent_runs.length === 0 ? (
              <p className="text-sm text-muted">{running ? "Agents are starting…" : "No agent runs recorded."}</p>
            ) : (
              <ol className="space-y-3">
                {item.agent_runs.map((run) => (
                  <li key={run.id} className="relative border-l border-line pl-3">
                    <span
                      className={`absolute -left-1 top-1.5 size-2 rounded-full ${
                        run.status === "completed" ? "bg-ok" : run.status === "failed" ? "bg-fail" : "bg-warn"
                      }`}
                      aria-hidden
                    />
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium capitalize">{run.agent_name.replaceAll("_", " ")}</p>
                      <Badge tone={run.status === "completed" ? "ok" : run.status === "failed" ? "fail" : "warn"}>
                        {run.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted">
                      {run.execution_time != null ? `${run.execution_time.toFixed(2)}s` : "—"}
                      {run.started_at ? ` · ${formatDate(run.started_at)}` : ""}
                    </p>
                    {run.error_message ? <p className="mt-1 text-xs text-fail">{run.error_message}</p> : null}
                  </li>
                ))}
              </ol>
            )}
          </Card>

          <Card>
            <CardTitle>Agent outputs</CardTitle>
            <p className="text-xs text-muted">
              Validated structured outputs. An agent that failed contributes nothing rather than a
              fabricated result.
            </p>
            <ul className="mt-3 space-y-2">
              {(result?.agent_status ?? []).map((agent) => (
                <li key={agent.agent} className="flex items-center justify-between text-xs">
                  <span className="capitalize">{agent.agent.replaceAll("_", " ")}</span>
                  <span className={agent.status === "completed" ? "text-ok" : agent.status === "failed" ? "text-fail" : "text-muted"}>
                    {agent.status}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

interface InvestigationResultJson {
  summary?: string;
  hypotheses?: Hypothesis[];
  recommended_actions?: string[];
  plan?: PlanItem[];
  limitations?: string[];
  ai?: { used: boolean; provider: string; note: string };
  evidence_verification?: { files_checked: number; issues: string[] };
  agent_status?: { agent: string; status: string; execution_time: number; error: string | null }[];
}

function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  return (
    <li className="rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{hypothesis.title}</p>
        <Badge tone={hypothesis.confidence >= 0.7 ? "ok" : hypothesis.confidence >= 0.4 ? "warn" : "neutral"}>
          {(hypothesis.confidence * 100).toFixed(0)}% confidence
        </Badge>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm text-muted">{hypothesis.reasoning}</p>
      <ul className="mt-2 space-y-1">
        {hypothesis.evidence.map((evidence, index) => (
          <li key={`${evidence.file}-${index}`} className="font-mono text-xs text-accent/90">
            {evidence.file}
            {evidence.start_line ? `:${evidence.start_line}` : ""}
            {evidence.end_line ? `–${evidence.end_line}` : ""}
            {evidence.note ? <span className="text-muted"> · {evidence.note}</span> : null}
          </li>
        ))}
      </ul>
      {hypothesis.suggested_check ? (
        <p className="mt-2 text-xs text-muted">Suggested check: {hypothesis.suggested_check}</p>
      ) : null}
    </li>
  );
}

function PlanCard({ item }: { item: PlanItem }) {
  return (
    <li className="rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={item.priority === "P0" ? "fail" : item.priority === "P1" ? "warn" : "neutral"}>{item.priority}</Badge>
        <p className="text-sm font-medium">{item.problem}</p>
        <span className="ml-auto text-xs text-muted">{item.complexity}</span>
      </div>
      <p className="mt-2 text-sm text-muted">{item.suggested_fix}</p>
      {item.related_files.length > 0 ? (
        <p className="mt-1 text-xs text-muted">Files: {item.related_files.join(", ")}</p>
      ) : null}
      {item.suggested_tests.length > 0 ? (
        <p className="mt-1 text-xs text-muted">Tests: {item.suggested_tests.join(", ")}</p>
      ) : null}
      {item.requires_human_approval ? (
        <p className="mt-1 text-[11px] text-warn">Requires human approval before implementation.</p>
      ) : null}
    </li>
  );
}
