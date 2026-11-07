import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { GitBranch, Maximize2, Search, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useGraph, useGraphMetrics } from "@/hooks/queries";
import { Badge, Button, Card, CardTitle, EmptyState, ErrorState, Loading, inputClass } from "@/components/ui";
import type { DependencyChain, GraphEdge, GraphNode, ImpactResult } from "@/types/api";

const typeColors: Record<string, string> = {
  file: "#7b82ff",
  module: "#67b8e3",
  class: "#e8c468",
  function: "#5fd39a",
  test: "#f2a1c0",
  workflow: "#c9a7ff",
  directory: "#8d95a8",
  repository: "#e7e9ef",
};

const edgeColors: Record<string, string> = {
  IMPORTS: "#7b82ff",
  CALLS: "#5fd39a",
  TESTS: "#f2a1c0",
  CONTAINS: "#3a4152",
  DEPENDS_ON: "#e8c468",
};

function layout(nodes: GraphNode[], edges: GraphEdge[]): Node[] {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const children = new Map<string, string[]>();
  const indegree = new Map(nodes.map((node) => [node.id, 0]));

  for (const edge of edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) continue;
    children.set(edge.source, [...(children.get(edge.source) ?? []), edge.target]);
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
  }

  const levels = new Map<string, number>();
  const queue = nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id);
  for (const id of queue) levels.set(id, 0);

  for (let index = 0; index < queue.length; index += 1) {
    const id = queue[index]!;
    for (const child of children.get(id) ?? []) {
      const nextLevel = Math.max(levels.get(child) ?? 0, (levels.get(id) ?? 0) + 1);
      levels.set(child, nextLevel);
      indegree.set(child, (indegree.get(child) ?? 1) - 1);
      if (indegree.get(child) === 0) queue.push(child);
    }
  }

  // Cycles and disconnected nodes still get a stable position instead of overlapping.
  let fallbackLevel = Math.max(0, ...levels.values()) + 1;
  for (const node of nodes) {
    if (!levels.has(node.id)) levels.set(node.id, fallbackLevel++);
  }

  const grouped = new Map<number, GraphNode[]>();
  for (const node of nodes) {
    const level = levels.get(node.id)!;
    grouped.set(level, [...(grouped.get(level) ?? []), node]);
  }

  return nodes.map((node) => {
    const level = levels.get(node.id)!;
    const row = grouped.get(level)!;
    const index = row.findIndex((item) => item.id === node.id);
    return {
    id: node.id,
    position: { x: index * 250, y: level * 155 },
    data: { label: `${node.name}${node.node_type === "file" ? "" : ` · ${node.node_type}`}` },
    style: {
      width: 190,
      border: `1px solid ${typeColors[node.node_type] ?? "#262b37"}`,
      borderLeft: `4px solid ${typeColors[node.node_type] ?? "#262b37"}`,
      background: "#151820",
      color: "#e7e9ef",
      fontSize: 11,
      borderRadius: 8,
      padding: "8px 10px",
    },
    };
  });
}

function toEdges(edges: GraphEdge[], showLabels: boolean): Edge[] {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    style: { stroke: edgeColors[edge.relationship_type] ?? "#3a4152", strokeWidth: 1.2, opacity: 0.7 },
    markerEnd: { type: MarkerType.ArrowClosed, color: edgeColors[edge.relationship_type] ?? "#3a4152", width: 14, height: 14 },
    label: showLabels ? edge.relationship_type : undefined,
    labelStyle: { fill: "#8d95a8", fontSize: 9 },
    labelBgStyle: { fill: "#0e1014", fillOpacity: 0.8 },
  }));
}

export function GraphPage() {
  return (
    <ReactFlowProvider>
      <GraphWorkspace />
    </ReactFlowProvider>
  );
}

function GraphWorkspace() {
  const { repositoryId } = useParams();
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [chain, setChain] = useState<{ direction: "dependencies" | "dependents" } | null>(null);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const graph = useGraph(repositoryId, { nodeTypes: typeFilter || undefined, search: search || undefined });
  const metrics = useGraphMetrics(repositoryId);
  const { fitView } = useReactFlow();

  const nodes = useMemo(
    () => layout(graph.data?.nodes ?? [], graph.data?.edges ?? []),
    [graph.data],
  );
  const edges = useMemo(() => toEdges(graph.data?.edges ?? [], (graph.data?.edges.length ?? 0) <= 60), [graph.data]);

  const chainQuery = useQuery({
    queryKey: ["graph", "chain", repositoryId, selected?.id, chain?.direction],
    queryFn: () => api.graph.dependencies(repositoryId!, selected!.id, chain!.direction, 3),
    enabled: Boolean(repositoryId && selected && chain),
  });

  const impactMutation = useMutation({
    mutationFn: () => api.graph.impact(repositoryId!, selected!.id, "dependents", 4),
    onSuccess: (result) => setImpact(result),
  });

  const highlightIds = useMemo(() => {
    if (impact) return new Set(impact.affected.map((item) => item.node.id));
    if (chainQuery.data) return new Set(chainQuery.data.steps.map((step) => step.node.id));
    return new Set<string>();
  }, [impact, chainQuery.data]);

  if (graph.isLoading) return <Loading label="Building graph view…" />;
  if (graph.isError) return <ErrorState message={graph.error.message} retry={() => void graph.refetch()} />;
  const data = graph.data!;

  if (data.nodes.length === 0) {
    return (
      <EmptyState icon={GitBranch} title="No graph nodes">
        Index the repository first, or clear the filters. Nodes come from parsed files and symbols.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Card className="p-3">
          <p className="text-xs text-muted">Nodes shown</p>
          <p className="text-xl font-semibold tabular-nums">{data.nodes.length}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted">Edges shown</p>
          <p className="text-xl font-semibold tabular-nums">{data.edges.length}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted">Detected cycles</p>
          <p className="text-xl font-semibold tabular-nums">{metrics.data?.cycle_count ?? "—"}</p>
        </Card>
        <Card className="p-3">
          <p className="text-xs text-muted">Total nodes</p>
          <p className="text-xl font-semibold tabular-nums">{data.node_total}</p>
        </Card>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search className="absolute left-3 top-2.5 size-4 text-muted" aria-hidden />
            <input
              aria-label="Search graph nodes"
              className={`${inputClass} pl-9`}
              placeholder="Search by file, symbol or qualified name"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <select
            aria-label="Filter by node type"
            className={`${inputClass} w-auto`}
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="">All node types</option>
            {["file", "module", "class", "function", "test", "workflow"].map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <Button variant="secondary" onClick={() => void fitView({ duration: 300, padding: 0.15 })}>
            <Maximize2 className="size-4" aria-hidden /> Reset view
          </Button>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-muted">
          {Object.entries(edgeColors).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1">
              <span className="inline-block h-0.5 w-4" style={{ background: color }} /> {type}
            </span>
          ))}
          {data.truncated ? <Badge tone="warn">View truncated at 250 nodes</Badge> : null}
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <Card className="h-[540px] overflow-hidden p-0">
          <ReactFlow
            nodes={nodes.map((node) => ({
              ...node,
              style: {
                ...node.style,
                opacity: highlightIds.size === 0 || highlightIds.has(node.id) || node.id === selected?.id ? 1 : 0.25,
              },
            }))}
            edges={edges}
            fitView
            minZoom={0.15}
            onNodeClick={(_, node) => {
              setSelected(data.nodes.find((item) => item.id === node.id) ?? null);
              setChain(null);
              setImpact(null);
            }}
            onPaneClick={() => setSelected(null)}
            nodesDraggable
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#262b37" gap={22} size={1} />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(node) => {
                const match = data.nodes.find((item) => item.id === node.id);
                return typeColors[match?.node_type ?? ""] ?? "#3a4152";
              }}
              maskColor="rgba(14,16,20,0.7)"
              style={{ background: "#151820" }}
            />
          </ReactFlow>
        </Card>

        <div className="space-y-3">
          <Card>
            <CardTitle>{selected ? "Node details" : "Select a node"}</CardTitle>
            {!selected ? (
              <p className="text-sm text-muted">
                Click a node to inspect its source location, direct dependencies and dependents, then
                run an impact analysis.
              </p>
            ) : (
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <Badge tone="accent">{selected.node_type}</Badge>
                  {selected.language ? <Badge>{selected.language}</Badge> : null}
                </div>
                <p className="break-words font-mono text-xs">{selected.qualified_name ?? selected.name}</p>
                {selected.file_path ? (
                  <p className="break-words text-xs text-muted">
                    {selected.file_path}
                    {selected.start_line ? `:${selected.start_line}` : ""}
                    {selected.end_line ? `–${selected.end_line}` : ""}
                  </p>
                ) : null}
                <p className="text-xs text-muted">
                  in-degree {selected.in_degree} · out-degree {selected.out_degree}
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button
                    variant="secondary"
                    className="px-2 py-1 text-xs"
                    onClick={() => {
                      setImpact(null);
                      setChain({ direction: "dependencies" });
                    }}
                  >
                    Dependencies
                  </Button>
                  <Button
                    variant="secondary"
                    className="px-2 py-1 text-xs"
                    onClick={() => {
                      setImpact(null);
                      setChain({ direction: "dependents" });
                    }}
                  >
                    Dependents
                  </Button>
                  <Button
                    className="px-2 py-1 text-xs"
                    onClick={() => impactMutation.mutate()}
                    disabled={impactMutation.isPending}
                  >
                    <ShieldAlert className="size-3.5" aria-hidden /> Impact
                  </Button>
                </div>
              </div>
            )}
          </Card>

          {chainQuery.isFetching ? <Loading label="Traversing graph…" /> : null}
          {chainQuery.isError ? <ErrorState message={chainQuery.error.message} /> : null}
          {chainQuery.data && !impact ? <ChainView chain={chainQuery.data} /> : null}
          {impact ? <ImpactView impact={impact} /> : null}
        </div>
      </div>
    </div>
  );
}

function ChainView({ chain }: { chain: DependencyChain }) {
  return (
    <Card>
      <CardTitle>{chain.direction === "dependencies" ? "Dependencies" : "Dependents"}</CardTitle>
      <p className="text-xs text-muted">{chain.explanation}</p>
      {chain.steps.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No relationships were found in this direction.</p>
      ) : (
        <ul className="mt-3 space-y-2 text-xs">
          {chain.steps.slice(0, 20).map((step) => (
            <li key={step.node.id + step.depth} className="rounded border border-line p-2">
              <p className="truncate font-mono">{step.node.file_path ?? step.node.name}</p>
              <p className="text-muted">
                depth {step.depth} · {step.via_edge?.relationship_type ?? "edge"}
                {step.via_edge ? ` · confidence ${step.via_edge.confidence.toFixed(2)}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
      {chain.truncated ? <p className="mt-2 text-xs text-warn">Traversal truncated at the configured depth.</p> : null}
    </Card>
  );
}

function ImpactView({ impact }: { impact: ImpactResult }) {
  return (
    <Card>
      <CardTitle action={<Badge tone={impact.affected.length > 0 ? "warn" : "ok"}>{impact.affected.length} affected</Badge>}>
        Impact analysis
      </CardTitle>
      <p className="text-xs text-muted">{impact.explanation}</p>
      {impact.related_tests.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wider text-muted">Related tests</p>
          <ul className="mt-1 space-y-1 text-xs">
            {impact.related_tests.map((test) => (
              <li key={test.id} className="font-mono">{test.file_path ?? test.name}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">No tests are linked to the affected nodes in the graph.</p>
      )}
      <ul className="mt-3 max-h-60 space-y-2 overflow-auto text-xs">
        {impact.affected.slice(0, 25).map((item) => (
          <li key={item.node.id} className="rounded border border-line p-2">
            <p className="truncate font-mono">{item.node.file_path ?? item.node.name}</p>
            <p className="text-muted">
              depth {item.depth} · {item.relationship} · confidence via{" "}
              {item.path.slice(0, 3).join(" → ") || item.node.name}
            </p>
          </li>
        ))}
      </ul>
      {impact.truncated ? <p className="mt-2 text-xs text-warn">Impact traversal was bounded.</p> : null}
      <p className="mt-2 text-[11px] text-muted">
        Severity is not implied by this list; it shows reachability from the selected node.
      </p>
    </Card>
  );
}
