"""Repository import and GitHub activity orchestration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import ensure_utc, utcnow
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.integrations.github import GitHubClient, GitHubRepoRef, parse_repository_url
from app.models.repository import Repository
from app.repositories import repos as repos_repo

ACTIVITY_CACHE_SECONDS = 600


def build_client(settings: Settings) -> GitHubClient:
    return GitHubClient(
        api_base=settings.github_api_base,
        raw_base=settings.github_raw_base,
        token=settings.github_token,
        timeout_seconds=settings.github_timeout_seconds,
        max_retries=settings.github_max_retries,
    )


def import_repository(
    session: Session,
    *,
    owner_id: str,
    url: str,
    branch: str | None,
    display_name: str | None,
    settings: Settings,
    client: GitHubClient | None = None,
) -> tuple[Repository, bool]:
    """Create (or return the existing) repository record for a validated GitHub URL.

    Returns (repository, created). Duplicate imports are idempotent: the same user importing
    the same repository twice gets the existing record instead of a second one.
    """
    ref = parse_repository_url(url)
    existing = repos_repo.get_by_full_name(session, owner_id, ref.full_name)
    if existing is not None:
        return existing, False

    owns_client = client is None
    github = client or build_client(settings)
    try:
        metadata = github.get_repository(ref)
        default_branch = metadata.get("default_branch") or "main"
        if branch:
            default_branch = branch
            github.get_branch(ref, branch)  # validates existence before persisting
    finally:
        if owns_client:
            github.close()

    if not metadata:
        raise NotFoundError("Repository not found on GitHub")
    if metadata.get("private"):
        # This build has no private-repository authorization; refuse rather than pretend.
        raise UnprocessableError(
            "Private repositories are not supported. "
            "Only public GitHub repositories can be imported."
        )
    record = repos_repo.create_repository(
        session,
        owner_id=owner_id,
        external_repository_id=str(metadata.get("id") or ""),
        name=display_name or metadata.get("name") or ref.repo,
        full_name=metadata.get("full_name") or ref.full_name,
        html_url=metadata.get("html_url") or ref.html_url,
        description=metadata.get("description"),
        default_branch=default_branch,
        visibility=metadata.get("visibility") or "public",
        language=metadata.get("language"),
        stars=int(metadata.get("stargazers_count") or 0),
        size_kb=int(metadata.get("size") or 0),
    )
    return record, True


def _iso(value: Any) -> str | None:
    """Normalise a GitHub timestamp to an ISO string (cache-safe, no datetime objects)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat()


def _serialise(items: list[dict], kind: str) -> list[dict]:
    if kind == "commits":
        return [
            {
                "sha": item["sha"],
                "short_sha": item["short_sha"],
                "message": item["message"],
                "author": item["author"],
                "authored_at": _iso(item.get("authored_at")),
                "url": item["url"],
            }
            for item in items
        ]
    if kind == "pull_requests":
        return [
            {
                **item,
                "created_at": _iso(item.get("created_at")),
                "updated_at": _iso(item.get("updated_at")),
            }
            for item in items
        ]
    return [{**item, "created_at": _iso(item.get("created_at"))} for item in items]


def get_activity(
    session: Session,
    repository: Repository,
    *,
    settings: Settings,
    client: GitHubClient | None = None,
    force: bool = False,
) -> dict:
    """Fetch activity, using a short database cache. Unavailable sections stay unavailable."""
    kinds = {
        "commits": lambda c: c.list_commits(ref, repository.default_branch),
        "pull_requests": lambda c: c.list_pull_requests(ref),
        "issues": lambda c: c.list_issues(ref),
        "workflows": lambda c: c.list_workflow_runs(ref),
    }
    ref = GitHubRepoRef(
        owner=repository.full_name.split("/")[0], repo=repository.full_name.split("/")[1]
    )
    cached = {kind: repos_repo.get_cached_activity(session, repository.id, kind) for kind in kinds}
    fresh_enough = all(
        record is not None
        and ensure_utc(record.fetched_at) > utcnow() - timedelta(seconds=ACTIVITY_CACHE_SECONDS)
        for record in cached.values()
    )
    if fresh_enough and not force:
        return {
            kind: {
                "available": record.available,
                "reason": record.unavailable_reason,
                "fetched_at": record.fetched_at,
                "items": record.payload.get("items", []),
            }
            for kind, record in cached.items()
            if record is not None
        }

    owns_client = client is None
    github = client or build_client(settings)
    sections: dict[str, dict] = {}
    try:
        for kind, fetcher in kinds.items():
            result = fetcher(github)
            payload = {"items": _serialise(result.items, kind)}
            repos_repo.cache_activity(
                session,
                repository_id=repository.id,
                kind=kind,
                payload=payload,
                available=result.available,
                reason=result.reason,
            )
            sections[kind] = {
                "available": result.available,
                "reason": result.reason,
                "fetched_at": utcnow(),
                "items": payload["items"],
            }
    finally:
        if owns_client:
            github.close()
    return sections


def activity_summary(full_name: str, sections: dict) -> str:
    available = [kind for kind, section in sections.items() if section["available"]]
    missing = [kind for kind, section in sections.items() if not section["available"]]
    if not available:
        return (
            f"GitHub activity for {full_name} could not be retrieved. "
            "No activity data is shown rather than inventing it."
        )
    parts = [f"GitHub activity for {full_name}: {', '.join(available)} retrieved."]
    if missing:
        parts.append(f"Unavailable: {', '.join(missing)} (see each section's reason).")
    return " ".join(parts)


def require_public_repository(repository: Repository) -> None:
    if repository.visibility != "public":
        raise ConflictError("Only public repositories are supported in this build")
