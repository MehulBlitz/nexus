"""Database access for repositories and snapshots, always scoped to an owner."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.repository import GitHubActivityCache, Repository, RepositorySnapshot


def create_repository(
    session: Session,
    *,
    owner_id: str,
    external_repository_id: str,
    name: str,
    full_name: str,
    html_url: str,
    description: str | None,
    default_branch: str,
    visibility: str,
    language: str | None,
    stars: int,
    size_kb: int,
) -> Repository:
    record = Repository(
        owner_id=owner_id,
        external_repository_id=external_repository_id,
        name=name,
        full_name=full_name,
        html_url=html_url,
        description=description,
        default_branch=default_branch,
        visibility=visibility,
        language=language,
        stars=stars,
        size_kb=size_kb,
        status="pending",
    )
    session.add(record)
    session.flush()
    return record


def get_owned(session: Session, owner_id: str, repository_id: str) -> Repository | None:
    record = session.get(Repository, repository_id)
    if record is None or record.owner_id != owner_id:
        return None
    return record


def get_by_full_name(
    session: Session, owner_id: str, full_name: str
) -> Repository | None:
    return session.scalar(
        select(Repository).where(
            Repository.owner_id == owner_id,
            Repository.provider == "github",
            func.lower(Repository.full_name) == full_name.lower(),
        )
    )


def list_owned(
    session: Session, owner_id: str, *, limit: int = 50, offset: int = 0
) -> tuple[list[Repository], int]:
    total = session.scalar(
        select(func.count()).select_from(Repository).where(Repository.owner_id == owner_id)
    )
    items = list(
        session.scalars(
            select(Repository)
            .where(Repository.owner_id == owner_id)
            .order_by(Repository.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, int(total or 0)


def delete_repository(session: Session, record: Repository) -> None:
    session.delete(record)


def latest_snapshot(session: Session, repository_id: str) -> RepositorySnapshot | None:
    return session.scalar(
        select(RepositorySnapshot)
        .where(RepositorySnapshot.repository_id == repository_id)
        .order_by(RepositorySnapshot.created_at.desc())
        .limit(1)
    )


def get_snapshot(
    session: Session, repository_id: str, snapshot_id: str
) -> RepositorySnapshot | None:
    record = session.get(RepositorySnapshot, snapshot_id)
    if record is None or record.repository_id != repository_id:
        return None
    return record


def create_snapshot(
    session: Session, *, repository_id: str, commit_sha: str, branch: str
) -> RepositorySnapshot:
    existing = session.scalar(
        select(RepositorySnapshot).where(
            RepositorySnapshot.repository_id == repository_id,
            RepositorySnapshot.commit_sha == commit_sha,
        )
    )
    if existing is not None:
        return existing
    record = RepositorySnapshot(
        repository_id=repository_id, commit_sha=commit_sha, branch=branch, indexing_status="pending"
    )
    session.add(record)
    session.flush()
    return record


def cache_activity(
    session: Session,
    *,
    repository_id: str,
    kind: str,
    payload: dict,
    available: bool,
    reason: str | None,
) -> GitHubActivityCache:
    existing = session.scalar(
        select(GitHubActivityCache).where(
            GitHubActivityCache.repository_id == repository_id,
            GitHubActivityCache.kind == kind,
        )
    )
    if existing is None:
        existing = GitHubActivityCache(repository_id=repository_id, kind=kind, payload=payload)
        session.add(existing)
    existing.payload = payload
    existing.available = available
    existing.unavailable_reason = reason
    existing.fetched_at = utcnow()
    session.flush()
    return existing


def get_cached_activity(
    session: Session, repository_id: str, kind: str
) -> GitHubActivityCache | None:
    return session.scalar(
        select(GitHubActivityCache).where(
            GitHubActivityCache.repository_id == repository_id,
            GitHubActivityCache.kind == kind,
        )
    )
