import { Download, FileText, Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useCreateReport, useReport, useReports } from "@/hooks/queries";
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
import clsx from "clsx";

export function ReportsPage() {
  const { repositoryId } = useParams();
  const reports = useReports(repositoryId);
  const create = useCreateReport(repositoryId!);
  const [title, setTitle] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const report = useReport(selectedId ?? undefined);

  if (reports.isLoading) return <Loading label="Loading reports…" />;
  if (reports.isError) return <ErrorState message={reports.error.message} retry={() => void reports.refetch()} />;
  const items = reports.data?.items ?? [];

  return (
    <div className="space-y-5">
      <Card>
        <CardTitle>Generate a report</CardTitle>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate(
              { title: title || undefined },
              {
                onSuccess: (created) => {
                  setTitle("");
                  setSelectedId(created.id);
                },
              },
            );
          }}
        >
          <div className="min-w-56 flex-1">
            <Field label="Report title" htmlFor="report-title" hint="Optional; defaults to a dated release review">
              <input
                id="report-title"
                className={inputClass}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Release review"
              />
            </Field>
          </div>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
            Generate
          </Button>
        </form>
        {create.isError ? <div className="mt-3"><ErrorState message={create.error.message} /></div> : null}
        <p className="mt-3 text-xs text-muted">
          Reports assemble the latest snapshot, risk summary, dependency observations and any
          investigation findings that already exist. Nothing is invented to fill a section.
        </p>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <Card>
          <CardTitle action={<Badge>{items.length}</Badge>}>Reports</CardTitle>
          {items.length === 0 ? (
            <EmptyState icon={FileText} title="No reports yet">
              Generate a report to capture the current snapshot.
            </EmptyState>
          ) : (
            <ul className="space-y-1">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={clsx(
                      "w-full rounded-lg px-2 py-2 text-left transition",
                      selectedId === item.id ? "bg-accent/10 text-accent" : "hover:bg-white/5",
                    )}
                  >
                    <p className="truncate text-sm font-medium">{item.title}</p>
                    <p className="text-xs text-muted">
                      {relativeTime(item.created_at)} · {item.snapshot_id ? item.snapshot_id.slice(0, 8) : "no snapshot"}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardTitle
            action={
              selectedId ? (
                <a
                  href={api.reports.export(selectedId)}
                  className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1 text-xs hover:border-accent/60"
                >
                  <Download className="size-3.5" aria-hidden /> Download Markdown
                </a>
              ) : null
            }
          >
            Report
          </CardTitle>
          {!selectedId ? (
            <EmptyState icon={FileText} title="Select a report">
              The rendered Markdown appears here. Download returns the exported .md file.
            </EmptyState>
          ) : report.isLoading ? (
            <Loading label="Loading report…" />
          ) : report.isError ? (
            <ErrorState message={report.error.message} retry={() => void report.refetch()} />
          ) : report.data ? (
            <div>
              <p className="mb-3 text-xs text-muted">
                {report.data.title} · generated {formatDate(report.data.created_at)}
              </p>
              <pre className="max-h-[640px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-ink/60 p-4 font-mono text-xs leading-relaxed">
                {report.data.markdown}
              </pre>
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
