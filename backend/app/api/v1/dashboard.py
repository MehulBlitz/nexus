"""Dashboard aggregates, all derived from stored records."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db
from app.core.config import get_settings
from app.models.investigation import Investigation, Report
from app.models.user import User
from app.repositories import investigations as inv_repo
from app.repositories import jobs as jobs_repo
from app.repositories import repos as repos_repo
from app.schemas.dashboard import AgentActivityOut, AuditEventOut, DashboardStats
from app.schemas.repository import RepositoryOut
from app.services import risk_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> DashboardStats:
    repositories, total = repos_repo.list_owned(db, user.id, limit=6, offset=0)
    all_repositories, all_total = repos_repo.list_owned(db, user.id, limit=200, offset=0)
    indexed_files = 0
    symbols = 0
    risk_distribution = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for repository in all_repositories:
        snapshot = repos_repo.latest_snapshot(db, repository.id)
        if snapshot is not None:
            indexed_files += snapshot.file_count
            symbols += snapshot.symbol_count
        summary = risk_service.risk_summary(db, repository)
        for severity, count in summary["severity_counts"].items():
            risk_distribution[severity] = risk_distribution.get(severity, 0) + count

    open_investigations = int(
        db.scalar(
            select(func.count())
            .select_from(Investigation)
            .where(
                Investigation.user_id == user.id,
                Investigation.status.in_(("queued", "running")),
            )
        )
        or 0
    )
    completed_investigations = int(
        db.scalar(
            select(func.count())
            .select_from(Investigation)
            .where(Investigation.user_id == user.id, Investigation.status == "completed")
        )
        or 0
    )
    report_count = int(
        db.scalar(
            select(func.count()).select_from(Report).where(Report.user_id == user.id)
        )
        or 0
    )
    owned_ids = [repository.id for repository in all_repositories]
    agent_runs = inv_repo.recent_agent_runs(db, owned_ids, limit=10)
    audit_events = jobs_repo.recent_audit(db, user.id, limit=10)
    settings = get_settings()
    return DashboardStats(
        repository_count=all_total,
        indexed_file_count=indexed_files,
        symbol_count=symbols,
        active_job_count=jobs_repo.count_active(db, user.id),
        open_investigation_count=open_investigations,
        completed_investigation_count=completed_investigations,
        report_count=report_count,
        risk_distribution=risk_distribution,
        repositories=[RepositoryOut.model_validate(item) for item in repositories],
        recent_activity=[
            AuditEventOut(
                id=event.id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                created_at=event.created_at,
            )
            for event in audit_events
        ],
        agent_activity=[
            AgentActivityOut(
                id=run.id,
                agent_name=run.agent_name,
                status=run.status,
                execution_time=run.execution_time,
                started_at=run.started_at,
                investigation_id=run.investigation_id,
            )
            for run in agent_runs
        ],
        ai_configured=settings.ai_provider != "none" and bool(settings.ai_model),
        ai_provider=settings.ai_provider,
    )
