"""Knowledge graph endpoints: view, node details, traversal, impact and metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, owned_repository
from app.core.errors import NotFoundError
from app.graph.engine import (
    build_view,
    connected_components,
    dependency_edges,
    find_cycles,
    impact_analysis,
    top_central,
    traversal,
)
from app.models.repository import Repository
from app.repositories import code as code_repo
from app.repositories import repos as repos_repo
from app.schemas.graph import (
    DependencyChain,
    GraphEdge,
    GraphMetrics,
    GraphNeighborhood,
    GraphNode,
    GraphResponse,
    ImpactRequest,
    ImpactResult,
    TraversalStep,
)

router = APIRouter(prefix="/repositories/{repository_id}/graph", tags=["graph"])

NODE_TYPES = {"repository", "directory", "file", "module", "class", "function", "test", "workflow"}
EDGE_TYPES = {"CONTAINS", "IMPORTS", "CALLS", "DEFINES", "TESTS", "DEPENDS_ON"}


def _load(db: Session, repository: Repository):
    snapshot = repos_repo.latest_snapshot(db, repository.id)
    if snapshot is None:
        raise NotFoundError("This repository has not been indexed yet")
    nodes = code_repo.nodes_for_snapshot(db, snapshot.id)
    edges = code_repo.edges_for_snapshot(db, snapshot.id)
    return snapshot, nodes, edges, build_view(nodes, edges)


def _node(view) -> GraphNode:
    return GraphNode(**view)


@router.get("", response_model=GraphResponse)
def graph_view(
    node_types: str | None = Query(default=None, description="Comma-separated node types"),
    relationship_types: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=300, ge=1, le=800),
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> GraphResponse:
    snapshot, nodes, edges, view = _load(db, repository)
    allowed_types = (
        {t for t in node_types.split(",") if t in NODE_TYPES} if node_types else set(NODE_TYPES)
    )
    allowed_edges = (
        {t for t in relationship_types.split(",") if t in EDGE_TYPES}
        if relationship_types
        else set(EDGE_TYPES)
    )
    selected = [
        node
        for node in nodes
        if node.node_type in allowed_types
        and (not search or search.lower() in (node.qualified_name or node.name).lower())
    ]
    if len(selected) > limit:
        # Keep the most connected nodes so the view stays informative when capped.
        selected_ids = {
            n.id for n in sorted(selected, key=lambda n: view.graph.in_degree(n.id), reverse=True)
        }
        selected = [n for n in selected if n.id in selected_ids][:limit]
    selected_ids = {node.id for node in selected}
    filtered_edges = [
        edge
        for edge in dependency_edges(view, allowed_edges)
        if edge.source_node_id in selected_ids and edge.target_node_id in selected_ids
    ]
    return GraphResponse(
        snapshot_id=snapshot.id,
        nodes=[_node(view.node_payload(node)) for node in selected],
        edges=[GraphEdge(**view.edge_payload(edge)) for edge in filtered_edges],
        truncated=len(nodes) > len(selected),
        node_total=len(nodes),
        edge_total=len(edges),
        filters={
            "node_types": sorted(allowed_types),
            "relationship_types": sorted(allowed_edges),
            "search": search,
            "limit": limit,
        },
    )


@router.get("/metrics", response_model=GraphMetrics)
def graph_metrics(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> GraphMetrics:
    _snapshot, nodes, edges, view = _load(db, repository)
    cycles = find_cycles(view, limit=100)
    central = top_central(view, limit=10)
    missing_evidence = sum(1 for edge in edges if not edge.evidence_json)
    return GraphMetrics(
        node_count=len(nodes),
        edge_count=len(edges),
        cycle_count=len(cycles),
        weakly_connected_components=connected_components(view),
        top_central=[
            {"path": path, "degree_centrality": round(degree, 4)}
            for path, degree, _between in central
        ],
        missing_evidence_edges=missing_evidence,
    )


@router.get("/nodes/{node_id}", response_model=GraphNeighborhood)
def node_detail(
    node_id: str,
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> GraphNeighborhood:
    _snapshot, _nodes, _edges, view = _load(db, repository)
    if node_id not in view.nodes:
        raise NotFoundError("Graph node not found")
    neighbours = set()
    for edge in view.edges:
        if edge.source_node_id == node_id:
            neighbours.add(edge.target_node_id)
        elif edge.target_node_id == node_id:
            neighbours.add(edge.source_node_id)
    neighbourhood = [view.nodes[node_id], *[view.nodes[n] for n in neighbours if n in view.nodes]]
    ids = {node.id for node in neighbourhood}
    return GraphNeighborhood(
        node=_node(view.node_payload(view.nodes[node_id])),
        nodes=[_node(view.node_payload(node)) for node in neighbourhood],
        edges=[
            GraphEdge(**view.edge_payload(edge))
            for edge in view.edges
            if edge.source_node_id in ids and edge.target_node_id in ids
        ],
    )


@router.get("/dependencies/{node_id}", response_model=DependencyChain)
def dependency_chain(
    node_id: str,
    direction: str = Query(default="dependencies", pattern="^(dependencies|dependents)$"),
    max_depth: int = Query(default=3, ge=1, le=8),
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> DependencyChain:
    _snapshot, _nodes, _edges, view = _load(db, repository)
    if node_id not in view.nodes:
        raise NotFoundError("Graph node not found")
    steps, truncated = traversal(
        view, node_id, direction="out" if direction == "dependencies" else "in", max_depth=max_depth
    )
    payload_steps: list[TraversalStep] = []
    for step in steps:
        edge = next(
            (
                e
                for e in view.edges
                if e.source_node_id == step["from_node_id"]
                and e.target_node_id == step["to_node_id"]
            ),
            None,
        )
        payload_steps.append(
            TraversalStep(
                node=_node(view.node_payload(view.nodes[step["node_id"]])),
                depth=step["depth"],
                via_edge=GraphEdge(**view.edge_payload(edge)) if edge else None,
                path=[view.nodes[p].name for p in step["path"] if p in view.nodes],
            )
        )
    return DependencyChain(
        root=_node(view.node_payload(view.nodes[node_id])),
        direction=direction,
        max_depth=max_depth,
        steps=payload_steps,
        truncated=truncated,
        explanation=(
            f"Breadth-first {direction} traversal bounded to {max_depth} level(s). "
            "Each step names the edge that produced it; confidence shows whether it was parsed "
            "or inferred."
        ),
    )


@router.post("/impact", response_model=ImpactResult)
def graph_impact(
    body: ImpactRequest,
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> ImpactResult:
    _snapshot, _nodes, _edges, view = _load(db, repository)
    node_id = body.node_id
    if node_id is None:
        if not body.file_path:
            raise NotFoundError("Provide node_id or file_path")
        matches = [
            node
            for node in view.nodes.values()
            if node.file_path == body.file_path and node.node_type in {"file", "test"}
        ]
        if not matches:
            raise NotFoundError("No indexed node matches that file path")
        node_id = matches[0].id
    if node_id not in view.nodes:
        raise NotFoundError("Graph node not found")
    result = impact_analysis(
        view, node_id, direction=body.direction, max_depth=body.max_depth
    )
    return ImpactResult(**result)
