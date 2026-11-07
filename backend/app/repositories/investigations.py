"""Database access for investigations, agent runs and reports."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.investigation import AgentRun, Investigation, Report


def create_investigation(
    session: Session,
    *,
    repository_id: str,
    user_id: str,
    question: str,
    scope_path: str | None,
    snapshot_id: str | None,
) -> Investigation:
    record = Investigation(
        repository_id=repository_id,
        user_id=user_id,
        question=question,
        scope_path=scope_path,
        snapshot_id=snapshot_id,
        status="queued",
    )
    session.add(record)
    session.flush()
    return record


def get_owned(
    session: Session, user_id: str, investigation_id: str, repository_id: str | None = None
) -> Investigation | None:
    record = session.get(Investigation, investigation_id)
    if record is None or record.user_id != user_id:
        return None
    if repository_id and record.repository_id != repository_id:
        return None
    return record


def list_for_repository(
    session: Session, repository_id: str, *, limit: int = 50, offset: int = 0
) -> tuple[list[Investigation], int]:
    total = int(
        session.scalar(
            select(func.count())
            .select_from(Investigation)
            .where(Investigation.repository_id == repository_id)
        )
        or 0
    )
    items = list(
        session.scalars(
            select(Investigation)
            .where(Investigation.repository_id == repository_id)
            .order_by(Investigation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def agent_runs(session: Session, investigation_id: str) -> list[AgentRun]:
    return list(
        session.scalars(
            select(AgentRun)
            .where(AgentRun.investigation_id == investigation_id)
            .order_by(AgentRun.started_at.asc().nullsfirst(), AgentRun.agent_name)
        )
    )


def recent_agent_runs(
    session: Session, repository_ids: list[str], *, limit: int = 50
) -> list[AgentRun]:
    if not repository_ids:
        return []
    return list(
        session.scalars(
            select(AgentRun)
            .join(Investigation, Investigation.id == AgentRun.investigation_id)
            .where(Investigation.repository_id.in_(repository_ids))
            .order_by(AgentRun.started_at.desc().nullslast())
            .limit(limit)
        )
    )


def create_report(
    session: Session,
    *,
    repository_id: str,
    user_id: str,
    snapshot_id: str | None,
    title: str,
    markdown: str,
) -> Report:
    record = Report(
        repository_id=repository_id,
        user_id=user_id,
        snapshot_id=snapshot_id,
        title=title,
        markdown=markdown,
    )
    session.add(record)
    session.flush()
    return record


def get_report(session: Session, user_id: str, report_id: str) -> Report | None:
    record = session.get(Report, report_id)
    if record is None or record.user_id != user_id:
        return None
    return record


def list_reports(
    session: Session, repository_id: str, *, limit: int = 50, offset: int = 0
) -> tuple[list[Report], int]:
    total = int(
        session.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.repository_id == repository_id)
        )
        or 0
    )
    items = list(
        session.scalars(
            select(Report)
            .where(Report.repository_id == repository_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total
