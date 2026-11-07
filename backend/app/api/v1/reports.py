"""Report generation, listing and Markdown export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, owned_repository, require_csrf
from app.core.errors import NotFoundError
from app.models.repository import Repository
from app.models.user import User
from app.repositories import investigations as inv_repo
from app.repositories import jobs as jobs_repo
from app.schemas.common import Page
from app.schemas.investigation import ReportCreate, ReportDetail, ReportOut
from app.services.report_service import generate_report

router = APIRouter(tags=["reports"])


@router.post(
    "/repositories/{repository_id}/reports", response_model=ReportDetail, status_code=201
)
def create_report(
    body: ReportCreate,
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    csrf=Depends(require_csrf),
) -> ReportDetail:
    report = generate_report(
        db,
        repository,
        user_id=user.id,
        title=body.title,
        investigation_id=body.investigation_id,
    )
    jobs_repo.audit(
        db,
        user_id=user.id,
        action="report.generated",
        resource_type="report",
        resource_id=report.id,
        metadata={"repository": repository.full_name},
    )
    db.commit()
    return ReportDetail(**ReportOut.model_validate(report).model_dump(), markdown=report.markdown)


@router.get("/repositories/{repository_id}/reports", response_model=Page[ReportOut])
def list_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> Page[ReportOut]:
    items, total = inv_repo.list_reports(db, repository.id, limit=limit, offset=offset)
    return Page[ReportOut](
        items=[ReportOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/reports/{report_id}", response_model=ReportDetail)
def report_detail(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ReportDetail:
    report = inv_repo.get_report(db, user.id, report_id)
    if report is None:
        raise NotFoundError("Report not found")
    return ReportDetail(
        **ReportOut.model_validate(report).model_dump(), markdown=report.markdown
    )


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    report = inv_repo.get_report(db, user.id, report_id)
    if report is None:
        raise NotFoundError("Report not found")
    filename = f"nexus-report-{report.id[:8]}.md"
    return Response(
        content=report.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
