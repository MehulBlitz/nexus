"""Shared context and deterministic tools available to agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.graph.engine import GraphView
from app.models.repository import Repository, RepositorySnapshot
from app.repositories import code as code_repo
from app.repositories import repos as repos_repo


@dataclass
class AgentContext:
    session: Session
    repository: Repository
    snapshot: RepositorySnapshot | None
    view: GraphView
    settings: Settings
    question: str = ""
    scope_path: str | None = None
    prior_results: dict[str, Any] = field(default_factory=dict)
    llm: Any | None = None

    @property
    def snapshot_id(self) -> str:
        return self.snapshot.id if self.snapshot else ""

    def file_nodes(self) -> list:
        return code_repo.nodes_for_snapshot(
            self.session, self.snapshot_id, node_types=["file", "test"]
        )

    def symbol_nodes(self) -> list:
        return code_repo.nodes_for_snapshot(
            self.session, self.snapshot_id, node_types=["function", "class"]
        )

    def file_line_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self.file_nodes():
            if node.file_path:
                metadata = node.metadata_json or {}
                counts[node.file_path] = int(metadata.get("line_count") or 0)
        return counts

    def snapshot_warnings(self) -> list[str]:
        return list(self.snapshot.warnings or []) if self.snapshot else []

    def parser_coverage(self) -> dict:
        return dict(self.snapshot.coverage or {}) if self.snapshot else {}

    def repository_name(self) -> str:
        return self.repository.full_name


def build_context(
    session: Session,
    *,
    repository_id: str,
    settings: Settings,
    question: str = "",
    scope_path: str | None = None,
    prior_results: dict[str, Any] | None = None,
    llm: Any | None = None,
) -> AgentContext:
    from app.graph.engine import build_view

    repository = session.get(Repository, repository_id)
    if repository is None:
        raise LookupError("Repository not found")
    snapshot = repos_repo.latest_snapshot(session, repository.id)
    nodes = (
        code_repo.nodes_for_snapshot(session, snapshot.id) if snapshot is not None else []
    )
    edges = (
        code_repo.edges_for_snapshot(session, snapshot.id) if snapshot is not None else []
    )
    return AgentContext(
        session=session,
        repository=repository,
        snapshot=snapshot,
        view=build_view(nodes, edges),
        settings=settings,
        question=question,
        scope_path=scope_path,
        prior_results=prior_results or {},
        llm=llm,
    )
