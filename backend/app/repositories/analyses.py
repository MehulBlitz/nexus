"""Database access for analysis runs and findings."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analysis import AnalysisRun, Finding


def create_run(
    session: Session,
    *,
    repository_id: str,
    user_id: str,
    analysis_type: str,
    snapshot_id: str | None,
    params: dict | None = None,
) -> AnalysisRun:
    run = AnalysisRun(
        repository_id=repository_id,
        user_id=user_id,
        analysis_type=analysis_type,
        snapshot_id=snapshot_id,
        params_json=params,
        status="queued",
    )
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, repository_id: str, run_id: str) -> AnalysisRun | None:
    record = session.get(AnalysisRun, run_id)
    if record is None or record.repository_id != repository_id:
        return None
    return record


def latest_completed_run(
    session: Session, repository_id: str, analysis_type: str
) -> AnalysisRun | None:
    return session.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.repository_id == repository_id,
            AnalysisRun.analysis_type == analysis_type,
            AnalysisRun.status == "completed",
        )
        .order_by(AnalysisRun.completed_at.desc())
        .limit(1)
    )


def findings_for_run(session: Session, run_id: str) -> list[Finding]:
    return list(
        session.scalars(
            select(Finding)
            .where(Finding.analysis_run_id == run_id)
            .order_by(Finding.risk_score.desc())
        )
    )


def latest_findings(session: Session, repository_id: str) -> list[Finding]:
    run = latest_completed_run(session, repository_id, "risk")
    if run is None:
        return []
    return findings_for_run(session, run.id)


def get_finding(session: Session, repository_id: str, finding_id: str) -> Finding | None:
    record = session.get(Finding, finding_id)
    if record is None or record.repository_id != repository_id:
        return None
    return record


def severity_counts(session: Session, run_id: str) -> dict[str, int]:
    rows = session.execute(
        select(Finding.severity, func.count())
        .where(Finding.analysis_run_id == run_id)
        .group_by(Finding.severity)
    ).all()
    return {severity: int(count) for severity, count in rows}
