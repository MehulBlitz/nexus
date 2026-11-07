"""Job type dispatch. Imports are local so the web process does not load heavy services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.job import Job


def dispatch(session: Session, job: Job, progress) -> dict:
    payload = job.payload_json or {}
    if job.job_type == "index_repository":
        from app.services.indexing_service import index_repository
        from app.services.repository_service import repository_for_job

        repository = repository_for_job(session, job)
        outcome = index_repository(session, repository, settings=_settings(), progress=progress)
        return {
            "snapshot_id": outcome.snapshot_id,
            "file_count": outcome.file_count,
            "symbol_count": outcome.symbol_count,
            "edge_count": outcome.edge_count,
        }
    if job.job_type == "run_risk_analysis":
        from app.services.repository_service import repository_for_job
        from app.services.risk_service import analyze_repository_risk

        repository = repository_for_job(session, job)
        run = analyze_repository_risk(
            session,
            repository,
            user_id=job.user_id or repository.owner_id,
            include_github_history=bool(payload.get("include_github_history", True)),
            max_findings=int(payload.get("max_findings", 25)),
            progress=progress,
        )
        return {"analysis_run_id": run.id}
    if job.job_type == "run_investigation":
        from app.orchestrator.orchestrator import run_investigation

        investigation_id = payload.get("investigation_id")
        if not investigation_id:
            raise ValueError("run_investigation job is missing investigation_id")
        run_investigation(session, investigation_id=investigation_id, progress=progress)
        return {"investigation_id": investigation_id}
    if job.job_type == "generate_report":
        from app.services.report_service import generate_report
        from app.services.repository_service import repository_for_job

        repository = repository_for_job(session, job)
        report = generate_report(
            session,
            repository,
            user_id=job.user_id or repository.owner_id,
            title=payload.get("title"),
            investigation_id=payload.get("investigation_id"),
        )
        return {"report_id": report.id}
    raise ValueError(f"Unknown job type: {job.job_type}")


def _settings():
    from app.core.config import get_settings

    return get_settings()
