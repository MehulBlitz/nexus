"""Graph algorithms over the persisted software graph.

NetworkX is used for cycles, centrality and components. Every traversal is bounded by an
explicit maximum depth and node budget so a large or adversarial graph cannot hang a request.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import networkx as nx

from app.models.code import CodeNode, DependencyEdge

MAX_TRAVERSAL_NODES = 500
DEFAULT_MAX_DEPTH = 4


@dataclass
class GraphView:
    nodes: dict[str, CodeNode]
    edges: list[DependencyEdge]
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)

    def node_payload(self, node: CodeNode) -> dict:
        return {
            "id": node.id,
            "node_type": node.node_type,
            "name": node.name,
            "qualified_name": node.qualified_name,
            "file_path": node.file_path,
            "start_line": node.start_line,
            "end_line": node.end_line,
            "language": node.language,
            "in_degree": int(self.graph.in_degree(node.id)) if node.id in self.graph else 0,
            "out_degree": int(self.graph.out_degree(node.id)) if node.id in self.graph else 0,
            "metadata": node.metadata_json or {},
        }

    def edge_payload(self, edge: DependencyEdge) -> dict:
        return {
            "id": edge.id,
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            "relationship_type": edge.relationship_type,
            "confidence": edge.confidence,
            "origin": edge.origin,
            "detail": edge.detail,
            "evidence": edge.evidence_json,
        }


def build_view(nodes: list[CodeNode], edges: list[DependencyEdge]) -> GraphView:
    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(node.id)
    node_ids = set(graph.nodes)
    valid_edges = [
        e
        for e in edges
        if e.source_node_id in node_ids and e.target_node_id in node_ids
    ]
    for edge in valid_edges:
        graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            relationship_type=edge.relationship_type,
            confidence=edge.confidence,
        )
    return GraphView(nodes={n.id: n for n in nodes}, edges=valid_edges, graph=graph)


def dependency_edges(view: GraphView, types: set[str] | None = None) -> list[DependencyEdge]:
    if types is None:
        return view.edges
    return [e for e in view.edges if e.relationship_type in types]


def traversal(
    view: GraphView,
    start_id: str,
    *,
    direction: str = "out",
    max_depth: int = DEFAULT_MAX_DEPTH,
    relationship_types: set[str] | None = None,
    max_nodes: int = MAX_TRAVERSAL_NODES,
) -> tuple[list[dict], bool]:
    """Breadth-first bounded traversal.

    Returns (steps, truncated). Steps contain the node id, depth, the edge used and the path.
    A node is visited at most once, so cyclic graphs always terminate.
    """
    if start_id not in view.graph:
        return [], False
    max_depth = max(1, min(int(max_depth), 8))
    seen = {start_id}
    queue: deque[tuple[str, int, list[str]]] = deque([(start_id, 0, [start_id])])
    steps: list[dict] = []
    truncated = False
    allowed = relationship_types
    while queue:
        current, depth, path = queue.popleft()
        if depth >= max_depth:
            continue
        neighbours = (
            view.graph.successors(current)
            if direction == "out"
            else view.graph.predecessors(current)
        )
        for neighbour in neighbours:
            edge_data = (
                view.graph.get_edge_data(current, neighbour)
                if direction == "out"
                else view.graph.get_edge_data(neighbour, current)
            )
            if allowed and edge_data and edge_data.get("relationship_type") not in allowed:
                continue
            if neighbour in seen:
                continue
            seen.add(neighbour)
            steps.append(
                {
                    "node_id": neighbour,
                    "depth": depth + 1,
                    # Edge direction, independent of traversal direction.
                    "edge_from": current if direction == "out" else neighbour,
                    "edge_to": neighbour if direction == "out" else current,
                    "from_node_id": current if direction == "out" else neighbour,
                    "to_node_id": neighbour if direction == "out" else current,
                    "path": [*path, neighbour],
                }
            )
            if len(steps) >= max_nodes:
                return steps, True
            queue.append((neighbour, depth + 1, [*path, neighbour]))
    return steps, truncated


def find_cycles(view: GraphView, *, limit: int = 50) -> list[list[str]]:
    """Simple cycles over dependency edges only, capped for safety."""
    dependency = nx.DiGraph()
    for edge in view.edges:
        if edge.relationship_type in {"IMPORTS", "CALLS", "DEPENDS_ON"}:
            dependency.add_edge(edge.source_node_id, edge.target_node_id)
    cycles: list[list[str]] = []
    for cycle in nx.simple_cycles(dependency, length_bound=8):
        cycles.append(list(cycle))
        if len(cycles) >= limit:
            break
    return cycles


def top_central(view: GraphView, *, limit: int = 10) -> list[tuple[str, float, float]]:
    """Return (node_id, degree_centrality, betweenness) for file-level nodes."""
    file_graph = nx.DiGraph()
    for edge in view.edges:
        source = view.nodes.get(edge.source_node_id)
        target = view.nodes.get(edge.target_node_id)
        if source and target and source.file_path and target.file_path:
            file_graph.add_edge(source.file_path, target.file_path)
    if file_graph.number_of_nodes() == 0:
        return []
    degree = nx.degree_centrality(file_graph)
    try:
        betweenness = nx.betweenness_centrality(file_graph, k=min(50, file_graph.number_of_nodes()))
    except Exception:  # noqa: BLE001 - metric failure must not break the report
        betweenness = dict.fromkeys(file_graph.nodes, 0.0)
    ranked = sorted(
        degree.items(), key=lambda item: (item[1], betweenness.get(item[0], 0.0)), reverse=True
    )[:limit]
    return [(path, score, betweenness.get(path, 0.0)) for path, score in ranked]


def connected_components(view: GraphView) -> int:
    return nx.number_weakly_connected_components(view.graph) if view.graph.number_of_nodes() else 0


def impact_analysis(
    view: GraphView,
    start_id: str,
    *,
    direction: str = "dependents",
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> dict:
    """Affected nodes with the evidence for each relationship."""
    root = view.nodes[start_id]
    directions = (
        [("out", "dependencies"), ("in", "dependents")]
        if direction == "both"
        else [("in" if direction == "dependents" else "out", direction)]
    )
    affected: list[dict] = []
    seen = {start_id}
    truncated = False
    max_depth_reached = 0
    for traversal_direction, _label in directions:
        steps, cut = traversal(
            view, start_id, direction=traversal_direction, max_depth=max_depth
        )
        truncated = truncated or cut
        for step in steps:
            if step["node_id"] in seen:
                continue
            seen.add(step["node_id"])
            node = view.nodes[step["node_id"]]
            if node.node_type not in {"file", "module", "test", "class", "function"}:
                continue
            affected.append(
                {
                    "node": view.node_payload(node),
                    "depth": step["depth"],
                    "path": [view.nodes[p].name for p in step["path"] if p in view.nodes],
                    "relationship": (
                        "depends on this change"
                        if traversal_direction == "in"
                        else "is required by it"
                    ),
                }
            )
            max_depth_reached = max(max_depth_reached, step["depth"])
    tests = [
        view.nodes[node_id]
        for node_id in seen
        if node_id in view.nodes and view.nodes[node_id].node_type == "test"
    ]
    evidence = [
        {
            "node": item["node"]["name"],
            "file": item["node"]["file_path"],
            "depth": item["depth"],
            "path": item["path"],
        }
        for item in affected[:25]
    ]
    return {
        "root": view.node_payload(root),
        "direction": direction,
        "max_depth": max_depth,
        "affected": affected,
        "related_tests": [view.node_payload(t) for t in tests],
        "depths_reached": max_depth_reached,
        "truncated": truncated,
        "explanation": (
            f"{len(affected)} node(s) are connected to {root.name} within depth {max_depth}. "
            "Each relationship is a parsed or inferred edge; inspect edge confidence for strength."
        ),
        "evidence": evidence,
    }
