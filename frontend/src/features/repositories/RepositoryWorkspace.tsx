import { ArrowLeft, GitBranch, Play, ShieldAlert, Sparkles, FileText } from "lucide-react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys, useRepository, useRepositoryStatus } from "@/hooks/queries";
import { Badge, Button, ErrorState, Loading, relativeTime } from "@/components/ui";
import clsx from "clsx";

const tabs = [
  { to: "", label: "Overview", end: true },
  { to: "graph", label: "Graph" },
  { to: "risks", label: "Risk center" },
  { to: "investigations", label: "Investigations" },
  { to: "reports", label: "Reports" },
];

export function RepositoryWorkspace() {
  const { repositoryId } = useParams();
  const repository = useRepository(repositoryId);
  const status = useRepositoryStatus(repositoryId, true);
  const client = useQueryClient();

  const index = useMutation({
    mutationFn: () => api.repositories.index(repositoryId!),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.repositoryStatus(repositoryId ?? "") });
      void client.invalidateQueries({ queryKey: queryKeys.repository(repositoryId ?? "") });
    },
  });

  if (repository.isLoading) return <Loading label="Loading repository…" />;
  if (repository.isError) {
    return <ErrorState message={repository.error.message} retry={() => void repository.refetch()} />;
  }
  const repo = repository.data!;
  const live = status.data;
  const active = live?.active_job && ["QUEUED", "RUNNING"].includes(live.active_job.status);
  const state = live?.status ?? repo.status;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/app/repositories" className="inline-flex items-center gap-1 text-xs text-muted hover:text-text">
          <ArrowLeft className="size-3" aria-hidden /> All repositories
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{repo.full_name}</h1>
              <Badge tone={state === "indexed" ? "ok" : state === "failed" ? "fail" : "warn"}>{state}</Badge>
            </div>
            <p className="mt-1 max-w-3xl text-sm text-muted">
              {repo.description || "No repository description."}
            </p>
            <p className="mt-1 text-xs text-muted">
              {repo.default_branch} · last indexed {relativeTime(repo.last_indexed_at)} ·{" "}
              <a href={repo.html_url} target="_blank" rel="noreferrer" className="hover:text-text">
                view on GitHub
              </a>
            </p>
          </div>
          <Button onClick={() => index.mutate()} disabled={index.isPending || Boolean(active)}>
            <Play className="size-4" aria-hidden />
            {active ? "Indexing…" : "Re-index"}
          </Button>
        </div>
      </div>

      {active && live?.active_job ? (
        <div className="rounded-lg border border-line bg-surface/60 p-3">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>{live.active_job.job_type.replaceAll("_", " ")}</span>
            <span>{live.active_job.progress}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
            <div className="h-full bg-accent transition-all" style={{ width: `${live.active_job.progress}%` }} />
          </div>
        </div>
      ) : null}
      {live?.last_error ? (
        <p className="rounded-lg border border-fail/30 bg-fail/5 p-3 text-sm text-fail">{live.last_error}</p>
      ) : null}

      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {tabs.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              clsx(
                "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm whitespace-nowrap",
                isActive ? "border-accent text-accent" : "border-transparent text-muted hover:text-text",
              )
            }
          >
            {tab.label === "Graph" ? <GitBranch className="size-3.5" aria-hidden /> : null}
            {tab.label === "Risk center" ? <ShieldAlert className="size-3.5" aria-hidden /> : null}
            {tab.label === "Investigations" ? <Sparkles className="size-3.5" aria-hidden /> : null}
            {tab.label === "Reports" ? <FileText className="size-3.5" aria-hidden /> : null}
            {tab.label}
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  );
}
