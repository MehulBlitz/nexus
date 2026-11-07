"""Code search over indexed metadata plus on-demand source fetching.

Source is not stored permanently. Content matches are found by fetching the current evidence
window from GitHub for the snapshot's commit, with a small in-memory cache and hard limits.
"""

from __future__ import annotations

import threading
import time

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.integrations.github import GitHubClient, GitHubRepoRef
from app.models.repository import Repository, RepositorySnapshot
from app.repositories import code as code_repo
from app.services.github_service import build_client

CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 300
MAX_CONTENT_FILES = 60
MAX_HITS = 50
SNIPPET_LENGTH = 200

_cache: dict[str, tuple[float, str | None]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str) -> tuple[bool, str | None]:
    with _cache_lock:
        entry = _cache.get(key)
    if entry is None:
        return False, None
    fetched_at, value = entry
    if time.time() - fetched_at > CACHE_TTL_SECONDS:
        with _cache_lock:
            _cache.pop(key, None)
        return False, None
    return True, value


def _cache_put(key: str, value: str | None) -> None:
    with _cache_lock:
        if len(_cache) >= CACHE_MAX_ENTRIES:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest, None)
        _cache[key] = (time.time(), value)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _repo_ref(repository: Repository) -> GitHubRepoRef:
    parts = repository.full_name.split("/")
    if len(parts) != 2:
        raise NotFoundError("Repository name is invalid")
    return GitHubRepoRef(owner=parts[0], repo=parts[1])


def _tokened(text: str, tokens: list[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if any(token in low for token in tokens):
            hits.append((number, line.strip()[:SNIPPET_LENGTH]))
    return hits


def search_code(
    session: Session,
    repository: Repository,
    snapshot: RepositorySnapshot | None,
    query: str,
    *,
    settings: Settings,
    language: str | None = None,
    directory: str | None = None,
    limit: int = 25,
    client: GitHubClient | None = None,
) -> list[dict]:
    """Return metadata and content matches, each labelled with its match_type."""
    tokens = [t for t in query.lower().split() if len(t) > 1][:6]
    if not tokens or snapshot is None:
        return []
    limit = max(1, min(limit, 100))
    directory = (directory or "").strip().strip("/")
    nodes = code_repo.nodes_for_snapshot(
        session, snapshot.id, node_types=["file", "test"]
    )
    results: list[dict] = []

    # 1. Path and symbol matches need no network access.
    for node in nodes:
        if language and node.language != language:
            continue
        if directory and not (node.file_path or "").startswith(directory + "/"):
            continue
        path = node.file_path or node.name
        if any(token in path.lower() for token in tokens):
            results.append(
                {
                    "path": path,
                    "language": node.language or "Unknown",
                    "line": 1,
                    "match_type": "path",
                    "snippet": path,
                    "symbol": None,
                }
            )
        if len(results) >= limit:
            return results
    symbol_nodes = code_repo.nodes_for_snapshot(
        session, snapshot.id, node_types=["function", "class"]
    )
    for node in symbol_nodes:
        name = (node.qualified_name or node.name).lower()
        if any(token in name for token in tokens):
            if directory and not (node.file_path or "").startswith(directory + "/"):
                continue
            results.append(
                {
                    "path": node.file_path or "",
                    "language": node.language or "Unknown",
                    "line": node.start_line or 1,
                    "match_type": "symbol",
                    "snippet": node.qualified_name or node.name,
                    "symbol": node.name,
                }
            )
            if len(results) >= limit:
                return results

    # 2. Content matches, bounded to candidate files and fetched on demand.
    candidates = [
        node
        for node in nodes
        if (not language or node.language == language)
        and (not directory or (node.file_path or "").startswith(directory + "/"))
    ]
    candidates.sort(key=lambda n: n.file_path or "")
    owns_client = client is None
    github = client or build_client(settings)
    try:
        for node in candidates[:MAX_CONTENT_FILES]:
            if len(results) >= limit:
                break
            path = node.file_path
            if not path:
                continue
            cache_key = f"{repository.id}:{snapshot.commit_sha}:{path}"
            cached, text = _cache_get(cache_key)
            if not cached:
                try:
                    text = github.fetch_file(
                        _repo_ref(repository),
                        snapshot.commit_sha,
                        path,
                        max_bytes=settings.max_file_bytes,
                    )
                except Exception:  # noqa: BLE001 - search degrades, it does not fail
                    text = None
                _cache_put(cache_key, text)
            if not text:
                continue
            for line_number, snippet in _tokened(text, tokens)[:5]:
                results.append(
                    {
                        "path": path,
                        "language": node.language or "Unknown",
                        "line": line_number,
                        "match_type": "content",
                        "snippet": snippet,
                        "symbol": None,
                    }
                )
                if len(results) >= limit:
                    break
    finally:
        if owns_client:
            github.close()
    return results[:limit]
