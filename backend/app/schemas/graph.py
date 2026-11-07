"""Knowledge-graph schemas: nodes, edges, traversal and impact analysis."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    node_type: str
    name: str
    qualified_name: str | None
    file_path: str | None
    start_line: int | None
    end_line: int | None
    language: str | None
    in_degree: int = 0
    out_degree: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: float
    origin: str
    detail: str | None = None
    evidence: dict[str, Any] | None = None


class GraphResponse(BaseModel):
    snapshot_id: str | None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool
    node_total: int
    edge_total: int
    filters: dict[str, Any]


class GraphNeighborhood(BaseModel):
    node: GraphNode
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TraversalStep(BaseModel):
    node: GraphNode
    depth: int
    via_edge: GraphEdge | None = None
    path: list[str] = Field(default_factory=list)
    relationship: str | None = None


class DependencyChain(BaseModel):
    root: GraphNode
    direction: Literal["dependencies", "dependents"]
    max_depth: int
    steps: list[TraversalStep]
    truncated: bool
    explanation: str


class CycleGroup(BaseModel):
    nodes: list[GraphNode]
    path: list[str]
    length: int


class GraphMetrics(BaseModel):
    node_count: int
    edge_count: int
    cycle_count: int
    weakly_connected_components: int
    top_central: list[dict[str, Any]]
    missing_evidence_edges: int


class ImpactRequest(BaseModel):
    node_id: str | None = None
    file_path: str | None = None
    direction: Literal["dependents", "dependencies", "both"] = "dependents"
    max_depth: int = Field(default=4, ge=1, le=8)


class ImpactResult(BaseModel):
    root: GraphNode
    direction: str
    max_depth: int
    affected: list[TraversalStep]
    related_tests: list[GraphNode]
    depths_reached: int
    truncated: bool
    explanation: str
    evidence: list[dict[str, Any]]
