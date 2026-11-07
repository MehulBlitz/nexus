"""Repository lookups shared by jobs and API routes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.job import Job
from app.models.repository import Repository, RepositorySnapshot
from app.repositories import repos as repos_repo


def repository_for_job(session: Session, job: Job) -> Repository:
    if not job.repository_id:
        raise NotFoundError("Job has no repository")
    record = session.get(Repository, job.repository_id)
    if record is None:
        raise NotFoundError("Repository no longer exists")
    return record


def require_repository(session: Session, repository_id: str) -> Repository:
    record = session.get(Repository, repository_id)
    if record is None:
        raise NotFoundError("Repository not found")
    return record


def latest_snapshot_or_none(session: Session, repository_id: str) -> RepositorySnapshot | None:
    return repos_repo.latest_snapshot(session, repository_id)
