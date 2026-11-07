"""System endpoints: liveness, readiness, version."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import check_database
from app.core.errors import error_body

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
