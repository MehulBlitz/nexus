"""Indexed code nodes and the evidence-carrying edges between them."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import new_id

NODE_TYPES = ("repository", "directory", "file", "module", "class", "function", "test", "workflow")
EDGE_TYPES = ("CONTAINS", "IMPORTS", "CALLS", "DEFINES", "TESTS", "DEPENDS_ON")


class CodeNode(Base):
    __tablename__ = "code_nodes"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "key", name="uq_code_node_snapshot_key"),
        Index("ix_code_nodes_snapshot_type", "snapshot_id", "node_type"),
        Index("ix_code_nodes_snapshot_file", "snapshot_id", "file_path"),
        Index("ix_code_nodes_qualified", "snapshot_id", "qualified_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("repository_snapshots.id", ondelete="CASCADE"), index=True
    )
    # Stable logical identifier inside a snapshot, e.g. "file:src/app.ts" or "function:x.y".
    key: Mapped[str] = mapped_column(String(500))
    node_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(300))
    qualified_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class DependencyEdge(Base):
    __tablename__ = "dependency_edges"
    __table_args__ = (
        Index("ix_edges_snapshot_source", "snapshot_id", "source_node_id"),
        Index("ix_edges_snapshot_target", "snapshot_id", "target_node_id"),
        Index("ix_edges_snapshot_type", "snapshot_id", "relationship_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("repository_snapshots.id", ondelete="CASCADE"), index=True
    )
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("code_nodes.id", ondelete="CASCADE"), index=True
    )
    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("code_nodes.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(20))
    # 1.0 = parsed directly; below 1.0 = inferred by name or path resolution.
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    origin: Mapped[str] = mapped_column(String(20), default="parsed")
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
