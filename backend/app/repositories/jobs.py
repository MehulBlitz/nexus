"""Database access for background jobs and audit records."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.job import AuditEvent, Job


def get_job(session: Session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def active_job_for(
    session: Session, repository_id: str, job_type: str | None = None
) -> Job | None:
    stmt = select(Job).where(
        Job.repository_id == repository_id, Job.status.in_(("QUEUED", "RUNNING"))
    )
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    return session.scalar(stmt.order_by(Job.created_at.desc()).limit(1))


def recent_for_repository(session: Session, repository_id: str, limit: int = 10) -> list[Job]:
    return list(
        session.scalars(
            select(Job)
            .where(Job.repository_id == repository_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
    )


def create_job(
    session: Session,
    *,
    job_type: str,
    repository_id: str | None,
    user_id: str | None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        repository_id=repository_id,
        user_id=user_id,
        payload_json=payload,
        dedupe_key=dedupe_key,
    )
    session.add(job)
    session.flush()
    return job


def claim_next_job(session: Session) -> Job | None:
    """Atomically claim the oldest queued job for this worker."""
    job = session.scalar(
        select(Job)
        .where(Job.status == "QUEUED")
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = "RUNNING"
    job.started_at = utcnow()
    job.attempts += 1
    session.flush()
    return job


def set_progress(session: Session, job: Job, progress: int) -> None:
    job.progress = max(0, min(100, int(progress)))
    session.flush()


def finish_job(session: Session, job: Job, *, result: dict | None = None) -> None:
    job.status = "COMPLETED"
    job.progress = 100
    job.result_json = result
    job.completed_at = utcnow()
    session.flush()


def fail_job(session: Session, job: Job, message: str) -> None:
    job.status = "FAILED"
    job.error_message = message[:2000]
    job.completed_at = utcnow()
    session.flush()


def cancel_job(session: Session, job: Job) -> None:
    job.status = "CANCELLED"
    job.completed_at = utcnow()
    session.flush()


def count_active(session: Session, owner_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.user_id == owner_id, Job.status.in_(("QUEUED", "RUNNING")))
        )
        or 0
    )


def audit(
    session: Session,
    *,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata,
    )
    session.add(event)
    session.flush()
    return event


def recent_audit(session: Session, user_id: str, limit: int = 20) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.user_id == user_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
    )
