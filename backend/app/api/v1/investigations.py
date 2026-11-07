"""Investigation endpoints, including server-sent progress events."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, owned_repository, require_csrf
from app.core.errors import ConflictError, NotFoundError
from app.models.investigation import Investigation
from app.models.repository import Repository
from app.models.user import User
from app.repositories import code as code_repo
from app.repositories import investigations as inv_repo
from app.repositories import jobs as jobs_repo
from app.repositories import repos as repos_repo
from app.schemas.common import Page
from app.schemas.investigation import (
    AgentRunOut,
    InvestigationCreate,
    InvestigationDetail,
    InvestigationOut,
)
from app.services import job_service

router = APIRouter(tags=["investigations"])


def _detail(db: Session, investigation: Investigation) -> InvestigationDetail:
    runs = inv_repo.agent_runs(db, investigation.id)
    data = InvestigationOut.model_validate(investigation).model_dump()
    return InvestigationDetail(
        **data,
        result=investigation.result_json,
        agent_runs=[AgentRunOut.model_validate(run) for run in runs],
    )


def _owned_investigation(
    investigation_id: str, db: Session, user: User, repository_id: str | None = None
) -> Investigation:
    record = inv_repo.get_owned(db, user.id, investigation_id, repository_id)
    if record is None:
        raise NotFoundError("Investigation not found")
    return record


@router.post(
    "/repositories/{repository_id}/investigations",
    response_model=InvestigationOut,
    status_code=202,
)
def create_investigation(
    body: InvestigationCreate,
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    csrf=Depends(require_csrf),
) -> InvestigationOut:
    snapshot = repos_repo.latest_snapshot(db, repository.id)
    if snapshot is None:
        raise ConflictError("Index the repository before investigating it")
    investigation = inv_repo.create_investigation(
        db,
        repository_id=repository.id,
        user_id=user.id,
        question=body.question.strip(),
        scope_path=body.scope_path,
        snapshot_id=snapshot.id,
    )
    job = job_service.enqueue(
        db,
        job_type="run_investigation",
        repository_id=repository.id,
        user_id=user.id,
        payload={"investigation_id": investigation.id},
        dedupe_key=f"investigation:{investigation.id}",
    )
    jobs_repo.audit(
        db,
        user_id=user.id,
        action="investigation.created",
        resource_type="investigation",
        resource_id=investigation.id,
    )
    db.commit()
    payload = InvestigationOut.model_validate(investigation)
    return payload.model_copy(update={"job_id": job.id})


@router.get(
    "/repositories/{repository_id}/investigations", response_model=Page[InvestigationOut]
)
def list_investigations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> Page[InvestigationOut]:
    items, total = inv_repo.list_for_repository(
        db, repository.id, limit=limit, offset=offset
    )
    return Page[InvestigationOut](
        items=[InvestigationOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetail)
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> InvestigationDetail:
    investigation = _owned_investigation(investigation_id, db, user)
    return _detail(db, investigation)


@router.post("/investigations/{investigation_id}/cancel", response_model=InvestigationDetail)
def cancel_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    csrf=Depends(require_csrf),
) -> InvestigationDetail:
    investigation = _owned_investigation(investigation_id, db, user)
    if investigation.status in {"completed", "failed", "cancelled"}:
        raise ConflictError("This investigation has already finished")
    investigation.status = "cancelled"
    from app.core.database import utcnow

    investigation.completed_at = utcnow()
    investigation.error_message = "Cancelled by the user"
    for run in inv_repo.agent_runs(db, investigation.id):
        if run.status in {"pending", "running"}:
            run.status = "skipped"
            run.error_message = "Investigation cancelled"
    jobs_repo.audit(
        db,
        user_id=user.id,
        action="investigation.cancelled",
        resource_type="investigation",
        resource_id=investigation.id,
    )
    db.commit()
    return _detail(db, investigation)


@router.get("/investigations/{investigation_id}/events")
async def investigation_events(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> StreamingResponse:
    _owned_investigation(investigation_id, db, user)
    user_id = user.id

    async def stream():
        from app.core.database import get_sessionmaker

        last_state = None
        sequence = 0
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            session = get_sessionmaker()()
            try:
                record = inv_repo.get_owned(session, user_id, investigation_id)
                if record is None:
                    yield "event: error\ndata: {\"message\": \"Investigation not found\"}\n\n"
                    return
                runs = inv_repo.agent_runs(session, record.id)
                state = {
                    "status": record.status,
                    "progress": record.progress,
                    "agents": [
                        {"agent": run.agent_name, "status": run.status} for run in runs
                    ],
                }
                if state != last_state:
                    sequence += 1
                    yield (
                        f"id: {sequence}\nevent: progress\n"
                        f"data: {json.dumps({'investigation_id': record.id, **state})}\n\n"
                    )
                    last_state = state
                if record.status in {"completed", "failed", "cancelled"}:
                    payload = json.dumps(
                        {"investigation_id": record.id, "status": record.status}
                    )
                    yield f"id: {sequence + 1}\nevent: done\ndata: {payload}\n\n"
                    return
            finally:
                session.close()
            await asyncio.sleep(1.0)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/investigations/{investigation_id}/evidence")
def investigation_evidence(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    investigation = _owned_investigation(investigation_id, db, user)
    result = investigation.result_json or {}
    references = [
        evidence
        for hypothesis in result.get("hypotheses", [])
        for evidence in hypothesis.get("evidence", [])
    ]
    snapshot = (
        db.get(repos_repo.RepositorySnapshot, investigation.snapshot_id)
        if investigation.snapshot_id
        else None
    )
    line_counts: dict[str, int] = {}
    if snapshot is not None:
        for node in code_repo.nodes_for_snapshot(
            db, snapshot.id, node_types=["file", "test"]
        ):
            if node.file_path:
                line_counts[node.file_path] = int(
                    (node.metadata_json or {}).get("line_count") or 0
                )
    return {
        "investigation_id": investigation.id,
        "references": references,
        "line_counts": line_counts,
        "limits": {
            "source_is_not_stored": True,
            "note": "Open the file on GitHub at the snapshot commit to read the cited lines.",
        },
    }
