import { Boxes, ExternalLink, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api, ApiError } from "@/lib/api";
import { queryKeys, useRepositories, useRepositoryStatus } from "@/hooks/queries";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  formatDate,
  inputClass,
  relativeTime,
} from "@/components/ui";

const importSchema = z.object({
  url: z
    .string()
    .trim()
    .min(1, "Repository URL is required")
    .refine((value) => /^https?:\/\/(www\.)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(value), {
      message: "Use a public repository URL such as https://github.com/owner/repository",
    }),
  branch: z.string().trim().max(100).optional(),
  displayName: z.string().trim().max(120).optional(),
});

export function RepositoriesPage() {
  const repositories = useRepositories();
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [importedId, setImportedId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const client = useQueryClient();

  const status = useRepositoryStatus(importedId ?? undefined, true);
  const finished = status.data?.status === "indexed" || status.data?.status === "failed";

  const importRepo = useMutation({
    mutationFn: (input: { url: string; branch?: string; display_name?: string }) =>
      api.repositories.import(input.url, input.branch, input.display_name),
    onSuccess: (repo) => {
      setImportedId(repo.id);
      setUrl("");
      setBranch("");
      setDisplayName("");
      setServerError(null);
      void client.invalidateQueries({ queryKey: queryKeys.repositories });
      void client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
    onError: (error) => {
      setServerError(error instanceof ApiError ? error.message : "Import failed");
    },
  });

  const reindex = useMutation({
    mutationFn: (id: string) => api.repositories.index(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.repositories });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.repositories.remove(id),
    onSuccess: () => {
      setConfirmDelete(null);
      void client.invalidateQueries({ queryKey: queryKeys.repositories });
      void client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setServerError(null);
    const parsed = importSchema.safeParse({ url, branch, displayName });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) next[String(issue.path[0])] = issue.message;
      setErrors(next);
      return;
    }
    setErrors({});
    importRepo.mutate({
      url: parsed.data.url,
      branch: parsed.data.branch || undefined,
      display_name: parsed.data.displayName || undefined,
    });
  };

  if (repositories.isLoading) return <Loading label="Loading repositories…" />;
  if (repositories.isError) {
    return <ErrorState message={repositories.error.message} retry={() => void repositories.refetch()} />;
  }
  const items = repositories.data?.items ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Repositories</h1>
        <p className="mt-1 text-sm text-muted">
          Import a public GitHub repository. NEXUS reads the tree at the latest commit, parses
          supported files and never executes repository code.
        </p>
      </header>

      <Card>
        <form onSubmit={submit} className="grid gap-3 lg:grid-cols-[2fr_1fr_1fr_auto]" noValidate>
          <Field label="GitHub repository URL" htmlFor="repo-url" error={errors.url}>
            <input
              id="repo-url"
              className={inputClass}
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              aria-invalid={Boolean(errors.url)}
            />
          </Field>
          <Field label="Branch" htmlFor="repo-branch" error={errors.branch} hint="Defaults to the repository default">
            <input
              id="repo-branch"
              className={inputClass}
              placeholder="main"
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
            />
          </Field>
          <Field label="Display name" htmlFor="repo-name" error={errors.displayName}>
            <input
              id="repo-name"
              className={inputClass}
              placeholder="Optional"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={importRepo.isPending} className="w-full lg:w-auto">
              {importRepo.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
              Import
            </Button>
          </div>
        </form>
        {serverError ? (
          <p className="mt-3 rounded-lg border border-fail/30 bg-fail/5 p-3 text-sm text-fail" role="alert">
            {serverError}
          </p>
        ) : null}
        <p className="mt-3 text-xs text-muted">
          Only github.com is accepted. Private repositories, write actions and arbitrary URL fetching
          are not supported in this release.
        </p>

        {importedId && status.data ? (
          <div className="mt-4 rounded-lg border border-line bg-ink/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>
                Indexing {status.data.latest_snapshot?.commit_sha.slice(0, 8) ?? ""} ·{" "}
                <Badge tone={status.data.status === "indexed" ? "ok" : status.data.status === "failed" ? "fail" : "warn"}>
                  {status.data.status}
                </Badge>
              </span>
              <Link to={`/app/repositories/${importedId}`} className="text-accent hover:underline">
                Open repository
              </Link>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className="h-full bg-accent transition-all"
                style={{ width: `${status.data.active_job?.progress ?? (finished ? 100 : 10)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-muted">
              {status.data.active_job
                ? `${status.data.active_job.job_type} · ${status.data.active_job.progress}%`
                : finished
                  ? "Indexing finished. The repository view has real file, symbol and graph data."
                  : "Waiting for the worker to pick up the job…"}
            </p>
            {status.data.last_error ? <p className="mt-1 text-xs text-fail">{status.data.last_error}</p> : null}
          </div>
        ) : null}
      </Card>

      {items.length === 0 ? (
        <EmptyState icon={Boxes} title="No repositories imported">
          Paste a public GitHub repository URL above to create the first snapshot.
        </EmptyState>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((repo) => (
            <Card key={repo.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Link to={`/app/repositories/${repo.id}`} className="truncate text-base font-medium hover:text-accent">
                    {repo.full_name}
                  </Link>
                  <p className="mt-1 line-clamp-2 text-sm text-muted">
                    {repo.description || "No description provided by GitHub."}
                  </p>
                </div>
                <Badge tone={repo.status === "indexed" ? "ok" : repo.status === "failed" ? "fail" : "warn"}>
                  {repo.status}
                </Badge>
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted">
                <div>
                  <dt>Default branch</dt>
                  <dd className="text-text">{repo.default_branch}</dd>
                </div>
                <div>
                  <dt>Language</dt>
                  <dd className="text-text">{repo.language ?? "—"}</dd>
                </div>
                <div>
                  <dt>Last indexed</dt>
                  <dd className="text-text">{relativeTime(repo.last_indexed_at)}</dd>
                </div>
                <div>
                  <dt>Imported</dt>
                  <dd className="text-text">{formatDate(repo.created_at)}</dd>
                </div>
              </dl>

              {repo.last_error ? <p className="mt-2 text-xs text-fail">{repo.last_error}</p> : null}

              <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
                <Link
                  to={`/app/repositories/${repo.id}`}
                  className="rounded-lg border border-line px-3 py-1.5 text-xs hover:border-accent/60"
                >
                  Open
                </Link>
                <Button variant="secondary" className="px-2.5 py-1.5 text-xs" onClick={() => reindex.mutate(repo.id)} disabled={reindex.isPending}>
                  <RefreshCw className="size-3.5" aria-hidden /> Re-index
                </Button>
                <a
                  href={repo.html_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-xs text-muted hover:text-text"
                >
                  <ExternalLink className="size-3.5" aria-hidden /> GitHub
                </a>
                {confirmDelete === repo.id ? (
                  <span className="ml-auto flex items-center gap-1.5">
                    <span className="text-xs text-fail">Delete all snapshots?</span>
                    <Button variant="danger" className="px-2.5 py-1.5 text-xs" onClick={() => remove.mutate(repo.id)} disabled={remove.isPending}>
                      Confirm
                    </Button>
                    <Button variant="ghost" className="px-2 py-1.5 text-xs" onClick={() => setConfirmDelete(null)}>
                      Cancel
                    </Button>
                  </span>
                ) : (
                  <Button variant="ghost" className="ml-auto px-2 py-1.5 text-xs" onClick={() => setConfirmDelete(repo.id)}>
                    <Trash2 className="size-3.5" aria-hidden /> Delete
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
