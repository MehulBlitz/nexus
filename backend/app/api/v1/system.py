"""System endpoints: liveness, readiness, version."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db
from app.core.config import get_settings
from app.core.database import check_database
from app.core.errors import NotFoundError, error_body
from app.models.job import Job
from app.models.user import User
from app.schemas.repository import JobOut

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    """Liveness only. Deliberately does not touch the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready():
    ok, error = check_database()
    if ok:
        return {"status": "ready", "checks": {"database": "ok"}}
    body = error_body("not_ready", "Service dependencies are unavailable")
    body["checks"] = {"database": f"failed: {error}"}
    return JSONResponse(body, status_code=503)


@router.get("/version")
def version() -> dict:
    s = get_settings()
    return {"name": s.app_name, "version": s.app_version, "environment": s.app_env}


@router.get("/jobs/{job_id}", response_model=JobOut)
def job_status(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> JobOut:
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise NotFoundError("Job not found")
    return JobOut.model_validate(job)
