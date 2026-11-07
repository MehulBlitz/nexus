import {
  AlertTriangle,
  ArrowUpRight,
  Braces,
  FileCode2,
  FolderTree,
  GitCommit,
  Search,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useActivity, useCodeSearch, useFiles, useOverview, useSymbolSearch } from "@/hooks/queries";
import {
  Badge,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  Loading,
  Stat,
  formatDate,
  inputClass,
  relativeTime,
} from "@/components/ui";
import type { ActivitySection } from "@/types/api";

const barColors = ["#7b82ff", "#5fd39a", "#e8c468", "#f2779b", "#67b8e3"];

export function RepositoryOverviewPage() {
  const { repositoryId } = useParams();
  const overview = useOverview(repositoryId);
  const activity = useActivity(repositoryId);
  const files = useFiles(repositoryId);
  const [symbolQuery, setSymbolQuery] = useState("");
  const [codeQuery, setCodeQuery] = useState("");
  const symbols = useSymbolSearch(repositoryId, symbolQuery);
  const code = useCodeSearch(repositoryId, codeQuery);

  if (overview.isLoading) return <Loading label="Loading code intelligence…" />;
  if (overview.isError) {
    return <ErrorState message={overview.error.message} retry={() => void overview.refetch()} />;
  }
  const data = overview.data!;

  if (!data.snapshot) {
    return (
      <EmptyState icon={FileCode2} title="No snapshot yet">
        Index this repository to parse source files, extract symbols and build the graph.
      </EmptyState>
    );
  }

  const languages = data.languages.map((item, index) => ({ ...item, fill: barColors[index % barColors.length] }));

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Files indexed" value={data.file_count} icon={FileCode2} hint={`${data.test_file_count} test files`} />
        <Stat label="Symbols" value={data.symbol_count} icon={Braces} hint={`${data.module_count} modules`} />
        <Stat label="Commit" value={data.snapshot.commit_sha.slice(0, 8)} icon={GitCommit} hint={data.snapshot.branch} />
        <Stat label="Warnings" value={data.warnings.length} icon={AlertTriangle} hint="Malformed files never fail the job" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardTitle>Language distribution</CardTitle>
          {languages.length === 0 ? (
            <EmptyState title="No supported source files found">
              The tree was fetched, but nothing matched the supported languages.
            </EmptyState>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={languages} margin={{ left: 4, right: 8, top: 4 }}>
                  <CartesianGrid vertical={false} stroke="#262b37" />
                  <XAxis dataKey="language" tick={{ fill: "#8d95a8", fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fill: "#8d95a8", fontSize: 11 }} width={28} />
                  <Tooltip
                    contentStyle={{ background: "#151820", border: "1px solid #262b37", fontSize: 12 }}
                    labelStyle={{ color: "#e7e9ef" }}
                  />
                  <Bar dataKey="files" radius={[4, 4, 0, 0]} fill="#7b82ff" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {data.languages.map((item) => (
              <Badge key={item.language} tone="neutral">
                {item.language} · {item.files} files · {item.percent}%
              </Badge>
            ))}
          </div>
        </Card>

        <Card>
          <CardTitle>Parser coverage</CardTitle>
          {data.parser_coverage.parse_modes ? (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {Object.entries(data.parser_coverage.parse_modes).map(([mode, count]) => (
                <div key={mode} className="rounded-lg border border-line p-3">
                  <dt className="text-xs uppercase tracking-wider text-muted">{mode}</dt>
                  <dd className="mt-1 text-xl font-semibold tabular-nums">{count}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-muted">Parser mode data is not available for this snapshot.</p>
          )}
          {data.parser_coverage.skipped_reasons ? (
            <div className="mt-3 space-y-1 text-xs text-muted">
              {Object.entries(data.parser_coverage.skipped_reasons).map(([reason, count]) => (
                <p key={reason}>
                  {reason.replaceAll("_", " ")}: <span className="text-text">{count}</span>
                </p>
              ))}
            </div>
          ) : null}
          {data.parser_coverage.analyzer_note ? (
            <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
              {data.parser_coverage.analyzer_note}
            </p>
          ) : null}
          <p className="mt-3 text-xs text-muted">
            Snapshot created {formatDate(data.snapshot.created_at)} · {data.snapshot.edge_count} graph
            edges.
          </p>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardTitle action={<Link to="graph" className="text-xs text-accent hover:underline">Open graph</Link>}>
            Module overview
          </CardTitle>
          {data.top_modules.length === 0 ? (
            <EmptyState icon={FolderTree} title="No module centrality available" />
          ) : (
            <ul className="space-y-2">
              {data.top_modules.slice(0, 8).map((item) => (
                <li key={item.path} className="flex items-center gap-3 text-sm">
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">{item.path}</span>
                  <span className="w-24 shrink-0">
                    <span className="block h-1.5 overflow-hidden rounded-full bg-line">
                      <span
                        className="block h-full bg-accent"
                        style={{ width: `${Math.min(100, item.degree_centrality * 100)}%` }}
                      />
                    </span>
                  </span>
                  <span className="w-10 shrink-0 text-right text-xs tabular-nums text-muted">
                    {(item.degree_centrality * 100).toFixed(0)}%
                  </span>
                </li>
              ))}
            </ul>
          )}
          {data.entry_points.length > 0 ? (
            <div className="mt-4 border-t border-line pt-3">
              <p className="text-xs uppercase tracking-wider text-muted">Entry points</p>
              <ul className="mt-2 space-y-1 font-mono text-xs">
                {data.entry_points.map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>

        <Card>
          <CardTitle>Parser warnings</CardTitle>
          {data.warnings.length === 0 ? (
            <p className="text-sm text-muted">No parser warnings for this snapshot.</p>
          ) : (
            <ul className="max-h-64 space-y-2 overflow-auto text-xs">
              {data.warnings.map((warning) => (
                <li key={warning} className="rounded border border-warn/20 bg-warn/5 p-2 text-warn/90">
                  {warning}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-muted">
            Lexer-based languages report declarations they could match; they are not full semantic
            parsers.
          </p>
        </Card>
      </div>

      <Card>
        <CardTitle>Source files</CardTitle>
        {files.isLoading ? (
          <Loading label="Loading files…" />
        ) : files.isError ? (
          <ErrorState message={files.error.message} />
        ) : (files.data?.items.length ?? 0) === 0 ? (
          <EmptyState icon={FileCode2} title="No indexed files" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="py-2 pr-3 font-medium">Path</th>
                  <th className="px-3 py-2 font-medium">Language</th>
                  <th className="px-3 py-2 text-right font-medium">Symbols</th>
                  <th className="px-3 py-2 text-right font-medium">Imports</th>
                  <th className="px-3 py-2 text-right font-medium">Lines</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {files.data!.items.slice(0, 60).map((file) => (
                  <tr key={file.node_id}>
                    <td className="max-w-md truncate py-2 pr-3 font-mono text-xs">{file.path}</td>
                    <td className="px-3 py-2 text-xs text-muted">{file.language}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{file.symbols}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{file.imports}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted">{file.line_count ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {files.data!.items.length > 60 ? (
              <p className="mt-2 text-xs text-muted">Showing the first 60 of {files.data!.total} files.</p>
            ) : null}
          </div>
        )}
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardTitle>Symbols</CardTitle>
          <label htmlFor="symbol-search" className="sr-only">
            Search symbols
          </label>
          <input
            id="symbol-search"
            className={inputClass}
            placeholder="Filter by name, class or function"
            value={symbolQuery}
            onChange={(event) => setSymbolQuery(event.target.value)}
          />
          <div className="mt-3 max-h-72 overflow-auto">
            {symbols.isLoading ? (
              <Loading label="Searching symbols…" />
            ) : (symbols.data?.items.length ?? 0) === 0 ? (
              <p className="py-4 text-sm text-muted">No symbols match this filter.</p>
            ) : (
              <ul className="divide-y divide-line text-sm">
                {symbols.data!.items.map((symbol) => (
                  <li key={symbol.id} className="flex items-center justify-between gap-2 py-2">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs">{symbol.qualified_name ?? symbol.name}</p>
                      <p className="truncate text-xs text-muted">
                        {symbol.file_path}
                        {symbol.start_line ? `:${symbol.start_line}` : ""}
                      </p>
                    </div>
                    <Badge>{symbol.node_type}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        <Card>
          <CardTitle>Code search</CardTitle>
          <label htmlFor="code-search" className="sr-only">
            Search code
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 size-4 text-muted" aria-hidden />
            <input
              id="code-search"
              className={`${inputClass} pl-9`}
              placeholder="Search paths, symbols and file contents (2+ characters)"
              value={codeQuery}
              onChange={(event) => setCodeQuery(event.target.value)}
            />
          </div>
          <div className="mt-3 max-h-72 overflow-auto">
            {codeQuery.trim().length < 2 ? (
              <p className="py-4 text-sm text-muted">Enter at least two characters to search.</p>
            ) : code.isLoading ? (
              <Loading label="Searching indexed and source files…" />
            ) : code.isError ? (
              <ErrorState message={code.error.message} />
            ) : (code.data?.length ?? 0) === 0 ? (
              <p className="py-4 text-sm text-muted">No matches.</p>
            ) : (
              <ul className="space-y-2 text-xs">
                {code.data!.slice(0, 25).map((hit) => (
                  <li key={`${hit.path}:${hit.line}:${hit.match_type}`} className="rounded border border-line p-2">
                    <p className="font-mono">
                      {hit.path}:{hit.line} <span className="text-muted">({hit.match_type})</span>
                    </p>
                    <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-muted">{hit.snippet}</pre>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">
            Content search fetches the file from GitHub at the indexed commit; source files are not
            stored permanently.
          </p>
        </Card>
      </div>

      <Card>
        <CardTitle
          action={
            activity.data ? (
              <span className="text-xs text-muted">Fetched {relativeTime(activity.data.commits.fetched_at)}</span>
            ) : null
          }
        >
          GitHub activity
        </CardTitle>
        {activity.isLoading ? (
          <Loading label="Reading repository activity…" />
        ) : activity.isError ? (
          <ErrorState message={activity.error.message} retry={() => void activity.refetch()} />
        ) : activity.data ? (
          <div className="grid gap-4 md:grid-cols-2">
            <ActivityList title="Recent commits" section={activity.data.commits} render={(item) => (
              <div className="min-w-0">
                <p className="truncate text-sm">{String(item.message ?? "Commit")}</p>
                <p className="text-xs text-muted">
                  {String(item.short_sha ?? "")} · {String(item.author ?? "unknown")} · {relativeTime(String(item.authored_at ?? ""))}
                </p>
              </div>
            )} />
            <ActivityList title="Pull requests" section={activity.data.pull_requests} render={(item) => (
              <div className="min-w-0">
                <p className="truncate text-sm">#{String(item.number)} {String(item.title ?? "")}</p>
                <p className="text-xs text-muted">
                  {String(item.state ?? "")} · {String(item.author ?? "")} · {relativeTime(String(item.updated_at ?? ""))}
                </p>
              </div>
            )} />
            <ActivityList title="Open issues" section={activity.data.issues} render={(item) => (
              <div className="min-w-0">
                <p className="truncate text-sm">#{String(item.number)} {String(item.title ?? "")}</p>
                <p className="text-xs text-muted">
                  {String(item.author ?? "")} · {relativeTime(String(item.created_at ?? ""))}
                </p>
              </div>
            )} />
            <ActivityList title="Workflow runs" section={activity.data.workflows} render={(item) => (
              <div className="min-w-0">
                <p className="truncate text-sm">{String(item.name ?? "Workflow")}</p>
                <p className="text-xs text-muted">
                  {String(item.status ?? "")} · {String(item.conclusion ?? "no conclusion")}
                </p>
              </div>
            )} />
          </div>
        ) : null}
        <p className="mt-3 text-xs text-muted">
          Activity is read live from the GitHub REST API. Unavailable or permission-restricted sections
          say so instead of showing invented data.
        </p>
      </Card>
    </div>
  );
}

function ActivityList({
  title,
  section,
  render,
}: {
  title: string;
  section: ActivitySection;
  render: (item: Record<string, unknown>) => React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium">{title}</h3>
        <Badge tone={section.available ? "ok" : "warn"}>{section.available ? `${section.items.length} items` : "unavailable"}</Badge>
      </div>
      {!section.available ? (
        <p className="rounded border border-warn/20 bg-warn/5 p-2 text-xs text-warn">{section.reason ?? "Not available"}</p>
      ) : section.items.length === 0 ? (
        <p className="text-xs text-muted">No items returned.</p>
      ) : (
        <ul className="space-y-2">
          {section.items.slice(0, 5).map((item, index) => (
            <li key={String(item.sha ?? item.id ?? item.number ?? index)} className="flex items-start gap-2">
              {render(item)}
              {typeof item.url === "string" ? (
                <a href={String(item.url)} target="_blank" rel="noreferrer" className="ml-auto shrink-0 text-muted hover:text-accent" aria-label="Open on GitHub">
                  <ArrowUpRight className="size-3.5" />
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
