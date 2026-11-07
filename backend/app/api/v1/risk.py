"""Risk analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, owned_repository, require_csrf
from app.core.errors import NotFoundError
from app.models.repository import Repository
from app.models.user import User
from app.repositories import analyses as analyses_repo
from app.repositories import jobs as jobs_repo
from app.schemas.risk import (
    RiskAnalyzeRequest,
    RiskFindingDetail,
    RiskFindingOut,
    RiskSignal,
    RiskSummary,
)
from app.services import job_service
from app.services.risk_service import risk_summary

router = APIRouter(prefix="/repositories/{repository_id}/risks", tags=["risk"])


@router.get("", response_model=list[RiskFindingOut])
def list_findings(
    limit: int = Query(default=50, ge=1, le=200),
    severity: str | None = Query(default=None, pattern="^(low|moderate|high|critical)$"),
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> list[RiskFindingOut]:
    findings = analyses_repo.latest_findings(db, repository.id)
    if severity:
        findings = [finding for finding in findings if finding.severity == severity]
    return [RiskFindingOut.model_validate(finding) for finding in findings[:limit]]


@router.get("/summary", response_model=RiskSummary)
def summary(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> RiskSummary:
    return RiskSummary(**risk_summary(db, repository))


@router.post("/analyze", status_code=202)
def analyze(
    body: RiskAnalyzeRequest,
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    csrf=Depends(require_csrf),
) -> dict:
    job = job_service.enqueue(
        db,
        job_type="run_risk_analysis",
        repository_id=repository.id,
        user_id=user.id,
        payload={
            "include_github_history": body.include_github_history,
            "max_findings": body.max_findings,
        },
        dedupe_key=f"risk:{repository.id}",
    )
    jobs_repo.audit(
        db,
        user_id=user.id,
        action="risk.analysis_requested",
        resource_type="repository",
        resource_id=repository.id,
    )
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{finding_id}", response_model=RiskFindingDetail)
def finding_detail(
    finding_id: str,
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> RiskFindingDetail:
    finding = analyses_repo.get_finding(db, repository.id, finding_id)
    if finding is None:
        raise NotFoundError("Finding not found")
    evidence = finding.evidence_json or {}
    signals = [
        RiskSignal(
            name=name,
            weight=float((evidence.get("weights") or {}).get(name, 0.0)),
            value=None,
            normalized=evidence.get("signals", {}).get(name),
            available=evidence.get("signals", {}).get(name) is not None,
            explanation=(
                "Measured and normalised to 0-100"
                if evidence.get("signals", {}).get(name) is not None
                else "Signal unavailable; excluded from the weighted score"
            ),
        )
        for name in sorted((evidence.get("signals") or {}).keys())
    ]
    return RiskFindingDetail(
        **RiskFindingOut.model_validate(finding).model_dump(), signals=signals
    )
