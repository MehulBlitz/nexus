"""Background job creation and execution.

Jobs are durable rows (a queue that survives a restart) and are executed either by this API
process in development ("inline") or by ``python -m app.workers.runner`` in worker mode.
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_sessionmaker, utcnow
from app.core.errors import ConflictError
from app.models.job import Job
from app.repositories import jobs as jobs_repo

logger = logging.getLogger("nexus.jobs")

JOB_TIMEOUT_SECONDS = 900


def enqueue(
    session: Session,
    *,
    job_type: str,
    repository_id: str | None,
    user_id: str | None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> Job:
    """Create a job, refusing to duplicate an in-flight job with the same dedupe key."""
    if dedupe_key:
        active = jobs_repo.active_job_for(session, repository_id or "", job_type)
        if active is not None:
            raise ConflictError("An identical job is already queued or running")
    job = jobs_repo.create_job(
        session,
        job_type=job_type,
        repository_id=repository_id,
        user_id=user_id,
        payload=payload or {},
        dedupe_key=dedupe_key,
    )
    session.commit()
    if get_settings().job_execution_mode == "inline":
        thread = threading.Thread(
            target=execute_job, args=(job.id,), name=f"nexus-job-{job.id[:8]}", daemon=True
        )
        thread.start()
    return job


def execute_job(job_id: str) -> None:
    """Run one job in a fresh session. Used by inline mode and the worker loop."""
    from app.workers.dispatch import dispatch

    session = get_sessionmaker()()
    started = time.monotonic()
    try:
        job = jobs_repo.get_job(session, job_id)
        if job is None:
            return
        if job.status != "QUEUED":
            return
        job.status = "RUNNING"
        job.started_at = job.started_at or utcnow()
        job.attempts += 1
        session.commit()

        def progress(percent: int, _message: str) -> None:
            job.progress = max(0, min(100, percent))
            session.commit()

        try:
            result = dispatch(session, job, progress)
            session.commit()
            jobs_repo.finish_job(session, job, result=result)
            session.commit()
        except Exception as exc:  # noqa: BLE001 - job failure is a recorded state
            session.rollback()
            job = jobs_repo.get_job(session, job_id)
            settings = get_settings()
            if job is not None:
                if job.attempts < settings.job_max_attempts and job.job_type != "index_repository":
                    job.status = "QUEUED"
                    job.error_message = f"Retry scheduled after {type(exc).__name__}"
                else:
                    jobs_repo.fail_job(session, job, str(exc) or type(exc).__name__)
                session.commit()
            logger.error("job %s failed", job_id, exc_info=exc)
    finally:
        elapsed = time.monotonic() - started
        if elapsed > JOB_TIMEOUT_SECONDS:
            logger.warning("job %s exceeded the soft time budget", job_id)
        session.close()


def poll_forever(poll_seconds: float | None = None) -> None:
    """Worker loop. Claims one queued job at a time until stopped."""
    settings = get_settings()
    interval = poll_seconds or settings.job_poll_seconds
    logger.info("nexus worker started")
    while True:
        session = get_sessionmaker()()
        try:
            job = jobs_repo.claim_next_job(session)
            session.commit()
            job_id = job.id if job else None
        except Exception:  # noqa: BLE001 - never kill the worker on a transient DB error
            session.rollback()
            job_id = None
            logger.exception("failed to claim a job")
        finally:
            session.close()
        if job_id:
            execute_job(job_id)
        else:
            time.sleep(interval)
