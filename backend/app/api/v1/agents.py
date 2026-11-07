"""Agent catalogue and execution history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import AGENT_CLASSES, ReviewPlanner
from app.api.deps import current_user, get_db
from app.core.errors import NotFoundError
from app.models.investigation import AgentRun, Investigation
from app.models.user import User
from app.repositories import investigations as inv_repo
from app.repositories import repos as repos_repo
from app.schemas.investigation import AgentDefinition, AgentRunGlobal, AgentRunOut

router = APIRouter(prefix="/agents", tags=["agents"])

DEFINITIONS = [
    AgentDefinition(
        name=agent.name,
        title=agent.title,
        responsibility=agent.responsibility,
        uses_llm_when_available=agent.uses_llm_when_available,
        output_schema=agent.output_model.__name__,
    )
    for agent in [*AGENT_CLASSES, ReviewPlanner]
]


@router.get("", response_model=list[AgentDefinition])
def list_agents() -> list[AgentDefinition]:
    return DEFINITIONS


@router.get("/runs", response_model=list[AgentRunGlobal])
def list_runs(
    repository_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AgentRunGlobal]:
    owned, _total = repos_repo.list_owned(db, user.id, limit=200, offset=0)
    owned_ids = [repo.id for repo in owned]
    if repository_id:
        if repository_id not in owned_ids:
            raise NotFoundError("Repository not found")
        owned_ids = [repository_id]
    runs = inv_repo.recent_agent_runs(db, owned_ids, limit=limit)
    investigations = {
        record.id: record
        for record in db.scalars(
            select(Investigation).where(
                Investigation.id.in_([run.investigation_id for run in runs] or [""])
            )
        )
    }
    payload: list[AgentRunGlobal] = []
    for run in runs:
        investigation = investigations.get(run.investigation_id)
        base = AgentRunOut.model_validate(run).model_dump()
        payload.append(
            AgentRunGlobal(
                **base,
                investigation_id=run.investigation_id,
                repository_id=investigation.repository_id if investigation else "",
                question=(investigation.question[:200] if investigation else None),
            )
        )
    return payload


@router.get("/runs/{run_id}", response_model=AgentRunGlobal)
def run_detail(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AgentRunGlobal:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise NotFoundError("Agent run not found")
    investigation = db.get(Investigation, run.investigation_id)
    if investigation is None or investigation.user_id != user.id:
        raise NotFoundError("Agent run not found")
    base = AgentRunOut.model_validate(run).model_dump()
    return AgentRunGlobal(
        **base,
        investigation_id=run.investigation_id,
        repository_id=investigation.repository_id,
        question=investigation.question[:200],
    )


@router.get("/stats")
def agent_stats(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[dict]:
    owned, _ = repos_repo.list_owned(db, user.id, limit=200, offset=0)
    ids = [repo.id for repo in owned]
    if not ids:
        return []
    rows = db.execute(
        select(
            AgentRun.agent_name,
            AgentRun.status,
            func.count(),
            func.avg(AgentRun.execution_time),
        )
        .join(Investigation, Investigation.id == AgentRun.investigation_id)
        .where(Investigation.repository_id.in_(ids))
        .group_by(AgentRun.agent_name, AgentRun.status)
    ).all()
    return [
        {
            "agent_name": name,
            "status": status,
            "count": int(count),
            "avg_execution_time": round(float(avg or 0), 3),
        }
        for name, status, count, avg in rows
    ]
