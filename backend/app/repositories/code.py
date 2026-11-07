"""Database access for indexed nodes and edges."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.code import CodeNode, DependencyEdge


def add_nodes(session: Session, nodes: list[CodeNode]) -> None:
    session.add_all(nodes)
    session.flush()


def add_edges(session: Session, edges: list[DependencyEdge]) -> None:
    session.add_all(edges)
    session.flush()


def nodes_for_snapshot(
    session: Session,
    snapshot_id: str,
    *,
    node_types: list[str] | None = None,
    file_path: str | None = None,
    limit: int | None = None,
) -> list[CodeNode]:
    stmt = select(CodeNode).where(CodeNode.snapshot_id == snapshot_id)
    if node_types:
        stmt = stmt.where(CodeNode.node_type.in_(node_types))
    if file_path:
        stmt = stmt.where(CodeNode.file_path == file_path)
    stmt = stmt.order_by(CodeNode.file_path, CodeNode.start_line)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def edges_for_snapshot(session: Session, snapshot_id: str) -> list[DependencyEdge]:
    stmt = select(DependencyEdge).where(DependencyEdge.snapshot_id == snapshot_id)
    return list(session.scalars(stmt))


def get_node(session: Session, snapshot_id: str, node_id: str) -> CodeNode | None:
    record = session.get(CodeNode, node_id)
    if record is None or record.snapshot_id != snapshot_id:
        return None
    return record


def get_node_by_key(session: Session, snapshot_id: str, key: str) -> CodeNode | None:
    return session.scalar(
        select(CodeNode).where(CodeNode.snapshot_id == snapshot_id, CodeNode.key == key)
    )


def nodes_by_ids(session: Session, snapshot_id: str, ids: list[str]) -> list[CodeNode]:
    if not ids:
        return []
    return list(
        session.scalars(
            select(CodeNode).where(
                CodeNode.snapshot_id == snapshot_id, CodeNode.id.in_(ids)
            )
        )
    )


def count_nodes(session: Session, snapshot_id: str, node_type: str | None = None) -> int:
    stmt = select(func.count()).select_from(CodeNode).where(CodeNode.snapshot_id == snapshot_id)
    if node_type:
        stmt = stmt.where(CodeNode.node_type == node_type)
    return int(session.scalar(stmt) or 0)


def count_edges(session: Session, snapshot_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(DependencyEdge)
            .where(DependencyEdge.snapshot_id == snapshot_id)
        )
        or 0
    )


def clear_snapshot_graph(session: Session, snapshot_id: str) -> None:
    session.execute(delete(DependencyEdge).where(DependencyEdge.snapshot_id == snapshot_id))
    session.execute(delete(CodeNode).where(CodeNode.snapshot_id == snapshot_id))
    session.flush()
