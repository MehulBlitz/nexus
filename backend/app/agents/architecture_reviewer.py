"""Architecture Reviewer: coupling, cycles, centrality and dependency direction."""

from __future__ import annotations

from app.agents.base import Agent
from app.agents.context import AgentContext
from app.agents.schemas import ArchitectureObservation, ArchitectureReviewResult, EvidenceRef
from app.graph.engine import find_cycles, top_central

# A lower layer must not import a higher layer. Violations are inferred from file paths only,
# so they are labelled inferred and never presented as certain defects.
LAYER_ORDER = {
    "models": 0,
    "schemas": 1,
    "repositories": 2,
    "analyzers": 2,
    "graph": 2,
    "services": 3,
    "agents": 4,
    "orchestrator": 5,
    "api": 6,
}
MAX_OBSERVATIONS = 8


def _layer_of(path: str) -> tuple[str | None, int | None]:
    for part in path.split("/"):
        if part in LAYER_ORDER:
            return part, LAYER_ORDER[part]
    return None, None


class ArchitectureReviewer(Agent):
    name = "architecture_reviewer"
    title = "Architecture Reviewer"
    responsibility = (
        "Detects circular dependencies, high-centrality modules and dependency-direction "
        "violations using the parsed graph. Style preferences are never reported as defects."
    )
    output_model = ArchitectureReviewResult

    def run(self, context: AgentContext) -> ArchitectureReviewResult:
        if not context.snapshot:
            return ArchitectureReviewResult(
                summary="No indexed snapshot is available for an architecture review.",
                limitations=["Index the repository first."],
            )
        cycles = find_cycles(context.view, limit=20)
        central = top_central(context.view, limit=8)
        observations: list[ArchitectureObservation] = []
        recommendations: list[str] = []
        limitations = [
            "Layer rules are heuristic path-name rules, not a declared architecture.",
            "Language analyzers do not resolve every import, so the graph is partial.",
        ]

        for cycle in cycles[:3]:
            paths = sorted(
                {
                    context.view.nodes[node_id].file_path or context.view.nodes[node_id].name
                    for node_id in cycle
                    if node_id in context.view.nodes
                }
            )
            observations.append(
                ArchitectureObservation(
                    title="Circular dependency detected",
                    detail=(
                        f"A dependency cycle involves {len(cycle)} node(s): "
                        f"{', '.join(paths[:6])}. Cycles make changes harder to reason about and "
                        "can hide import-order bugs."
                    ),
                    severity="moderate",
                    evidence=[
                        EvidenceRef(file=path, start_line=1, note="participant in a detected cycle")
                        for path in paths[:6]
                    ],
                    origin="measured",
                )
            )
            recommendations.append(
                "Break the cycle by extracting shared code into a lower-level module."
            )

        for path, degree, betweenness in central[:3]:
            observations.append(
                ArchitectureObservation(
                    title="High-centrality module",
                    detail=(
                        f"{path} has degree centrality {degree:.2f} and betweenness "
                        f"{betweenness:.2f} in the file dependency graph. Changes here have wide "
                        "reach; treat it as a structural hotspot rather than a defect."
                    ),
                    severity="info" if degree < 0.5 else "low",
                    evidence=[EvidenceRef(file=path, start_line=1, note="centrality measurement")],
                    origin="measured",
                )
            )
        if central:
            recommendations.append(
                f"Review {central[0][0]} carefully: it is the most connected module."
            )

        violations = 0
        for edge in context.view.edges:
            if edge.relationship_type != "IMPORTS":
                continue
            source = context.view.nodes.get(edge.source_node_id)
            target = context.view.nodes.get(edge.target_node_id)
            if not source or not target or not source.file_path or not target.file_path:
                continue
            source_layer, source_rank = _layer_of(source.file_path)
            target_layer, target_rank = _layer_of(target.file_path)
            if (
                source_rank is not None
                and target_rank is not None
                and target_rank > source_rank
                and source_layer != target_layer
            ):
                violations += 1
                if len(observations) < MAX_OBSERVATIONS:
                    observations.append(
                        ArchitectureObservation(
                            title="Dependency points to a higher layer",
                            detail=(
                                f"{source.file_path} ({source_layer}) imports "
                                f"{target.file_path} ({target_layer}). This is inferred from path "
                                "names; confirm against the project's intended architecture."
                            ),
                            severity="low",
                            evidence=[
                                EvidenceRef(
                                    file=source.file_path,
                                    start_line=edge.source_line or 1,
                                    note=edge.detail or "import edge",
                                ),
                                EvidenceRef(
                                    file=target.file_path,
                                    start_line=1,
                                    note="import target",
                                ),
                            ],
                            origin="inferred",
                        )
                    )
        if violations:
            recommendations.append(
                "Move shared abstractions downward instead of importing upward across layers."
            )

        summary = (
            f"Architecture review of {context.repository.full_name}: {len(cycles)} dependency "
            f"cycle(s), {len(central)} ranked central module(s), {violations} possible "
            "dependency-direction violation(s). Findings are structural observations backed by "
            "graph edges, not style opinions."
        )
        if not observations:
            observations.append(
                ArchitectureObservation(
                    title="No structural problems detected",
                    detail=(
                        "No dependency cycles and no high-centrality or direction anomalies were "
                        "found within the indexed graph."
                    ),
                    severity="info",
                    origin="measured",
                )
            )
            recommendations.append("Continue monitoring structure as the repository grows.")
        return ArchitectureReviewResult(
            summary=summary,
            observations=observations[:MAX_OBSERVATIONS],
            cycle_count=len(cycles),
            high_centrality=[path for path, _degree, _between in central],
            recommendations=recommendations,
            limitations=limitations,
        )
