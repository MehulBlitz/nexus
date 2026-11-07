"""GitHub REST integration for public repositories.

Security notes:
- The request host is never taken from user input. Only a validated owner/repo pair and a
  commit SHA are interpolated into URLs built on configured base URLs, which prevents SSRF.
- File paths come from GitHub's tree response and are re-validated before use.
- Repository content is fetched, never executed.
"""

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import NotFoundError, UnprocessableError, UpstreamError

OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})$")
SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
ALLOWED_HOSTS = {"github.com", "www.github.com"}


@dataclass(frozen=True)
class GitHubRepoRef:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def html_url(self) -> str:
        return f"https://github.com/{self.full_name}"


@dataclass
class GitHubFile:
    path: str
    sha: str
    size: int


@dataclass
class GitHubTree:
    files: list[GitHubFile]
    truncated: bool
    total_entries: int


@dataclass
class ActivityResult:
    available: bool
    reason: str | None = None
    items: list[dict[str, Any]] = field(default_factory=list)


def parse_repository_url(raw: str) -> GitHubRepoRef:
    """Validate a GitHub web URL and extract owner/repo.

    Rejects every other host, scheme, credential, query string and extra path segment.
    """
    value = (raw or "").strip()
    if not value:
        raise UnprocessableError("Repository URL is required")
    if not value.startswith("https://"):
        raise UnprocessableError("Repository URL must start with https://github.com/")
    rest = value[len("https://") :]
    if "@" in rest.split("/")[0]:
        raise UnprocessableError("Repository URL must not contain credentials")
    host, _, path = rest.partition("/")
    host = host.split(":")[0].lower()
    if host not in ALLOWED_HOSTS:
        raise UnprocessableError("Only github.com repository URLs are supported")
    if any(ch in path for ch in "?#"):
        raise UnprocessableError("Repository URL must not contain query strings or fragments")
    segments = [s for s in path.strip("/").split("/") if s]
    if len(segments) != 2:
        raise UnprocessableError("Repository URL must look like https://github.com/owner/repository")
    owner, repo = segments
    if repo.endswith(".git"):
        repo = repo[:-4]
    for label, part in (("owner", owner), ("repository", repo)):
        if not OWNER_REPO_RE.match(part) or part in {".", ".."}:
            raise UnprocessableError(f"Invalid GitHub {label} name")
    return GitHubRepoRef(owner=owner, repo=repo)


def validate_file_path(path: str) -> str:
    """Reject absolute, traversal or control-character paths from untrusted API data."""
    if not path or len(path) > 900:
        raise UnprocessableError("Invalid repository file path")
    if path.startswith("/") or ".." in path.split("/") or "\\" in path:
        raise UnprocessableError("Invalid repository file path")
    if any(ord(ch) < 32 for ch in path):
        raise UnprocessableError("Invalid repository file path")
    return path


class GitHubClient:
    """Synchronous GitHub client with bounded retries and explicit error mapping."""

    def __init__(
        self,
        *,
        api_base: str,
        raw_base: str,
        token: str = "",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "nexus-engineering-intelligence",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=api_base.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )
        self._raw_base = raw_base.rstrip("/")
        self._max_retries = max_retries
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- internals ---------------------------------------------------------
    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(path, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    self._sleep(0.4 * (attempt + 1))
                    continue
                raise UpstreamError("GitHub is unreachable. Try again shortly.") from exc
            if response.status_code == 200:
                return response.json()
            if response.status_code in {500, 502, 503, 504} and attempt < self._max_retries:
                self._sleep(0.4 * (attempt + 1))
                continue
            raise self._map_error(response)
        raise UpstreamError("GitHub request failed") from last_error

    @staticmethod
    def _map_error(response: httpx.Response) -> Exception:
        status = response.status_code
        if status == 404:
            return NotFoundError("Repository or resource not found on GitHub (it must be public)")
        if status in {403, 429}:
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            if remaining == "0":
                when = ""
                if reset and reset.isdigit():
                    reset_at = datetime.fromtimestamp(int(reset), UTC)
                    when = f" Resets at {reset_at.strftime('%H:%M UTC')}."
                return UpstreamError(f"GitHub API rate limit reached.{when}")
            return UpstreamError("GitHub refused the request (access restricted or rate limited)")
        if status == 401:
            return UpstreamError("GitHub credentials are invalid")
        return UpstreamError(f"GitHub returned HTTP {status}")

    # --- public API ---------------------------------------------------------
    def get_repository(self, ref: GitHubRepoRef) -> dict[str, Any]:
        return self._request(f"/repos/{ref.owner}/{ref.repo}")

    def get_branch(self, ref: GitHubRepoRef, branch: str) -> dict[str, Any]:
        if not BRANCH_RE.match(branch) or ".." in branch:
            raise UnprocessableError("Invalid branch name")
        return self._request(f"/repos/{ref.owner}/{ref.repo}/branches/{quote(branch, safe='/')}")

    def get_tree(self, ref: GitHubRepoRef, sha: str, *, max_entries: int = 4000) -> GitHubTree:
        if not SHA_RE.match(sha):
            raise UnprocessableError("Invalid commit SHA")
        data = self._request(
            f"/repos/{ref.owner}/{ref.repo}/git/trees/{sha}", params={"recursive": "1"}
        )
        entries = data.get("tree") or []
        files = [
            GitHubFile(path=e["path"], sha=e.get("sha", ""), size=int(e.get("size") or 0))
            for e in entries
            if e.get("type") == "blob" and isinstance(e.get("path"), str)
        ][:max_entries]
        return GitHubTree(
            files=files, truncated=bool(data.get("truncated")), total_entries=len(entries)
        )

    def fetch_file(
        self, ref: GitHubRepoRef, sha: str, path: str, *, max_bytes: int
    ) -> str | None:
        """Fetch one text file. Returns None when the file exceeds max_bytes."""
        path = validate_file_path(path)
        if not SHA_RE.match(sha):
            raise UnprocessableError("Invalid commit SHA")
        url = (
            f"{self._raw_base}/{quote(ref.owner, safe='')}/{quote(ref.repo, safe='')}/"
            f"{sha}/{quote(path, safe='/')}"
        )
        try:
            with self._client.stream("GET", url) as response:
                if response.status_code == 404:
                    return None
                if response.status_code != 200:
                    self._map_error(response)
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        return None
                    chunks.append(chunk)
        except httpx.HTTPError:
            return None
        raw = b"".join(chunks)
        if b"\x00" in raw:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    # --- activity ----------------------------------------------------------
    def list_commits(self, ref: GitHubRepoRef, branch: str, limit: int = 15) -> ActivityResult:
        try:
            data = self._request(
                f"/repos/{ref.owner}/{ref.repo}/commits", params={"sha": branch, "per_page": limit}
            )
        except (UpstreamError, NotFoundError) as exc:
            return ActivityResult(False, exc.message)
        items = [
            {
                "sha": c.get("sha", ""),
                "short_sha": (c.get("sha") or "")[:7],
                "message": ((c.get("commit") or {}).get("message") or "").split("\n")[0][:300],
                "author": ((c.get("commit") or {}).get("author") or {}).get("name"),
                "authored_at": ((c.get("commit") or {}).get("author") or {}).get("date"),
                "url": c.get("html_url", ""),
            }
            for c in data
        ]
        return ActivityResult(True, items=items)

    def list_pull_requests(self, ref: GitHubRepoRef, limit: int = 15) -> ActivityResult:
        try:
            data = self._request(
                f"/repos/{ref.owner}/{ref.repo}/pulls",
                params={"state": "all", "per_page": limit, "sort": "updated", "direction": "desc"},
            )
        except (UpstreamError, NotFoundError) as exc:
            return ActivityResult(False, exc.message)
        items = [
            {
                "number": p.get("number"),
                "title": p.get("title", ""),
                "state": p.get("state", "unknown"),
                "user": (p.get("user") or {}).get("login"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "url": p.get("html_url", ""),
                "draft": bool(p.get("draft")),
            }
            for p in data
        ]
        return ActivityResult(True, items=items)

    def list_issues(self, ref: GitHubRepoRef, limit: int = 15) -> ActivityResult:
        try:
            data = self._request(
                f"/repos/{ref.owner}/{ref.repo}/issues",
                params={"state": "open", "per_page": limit},
            )
        except (UpstreamError, NotFoundError) as exc:
            return ActivityResult(False, exc.message)
        items = [
            {
                "number": i.get("number"),
                "title": i.get("title", ""),
                "state": i.get("state", "unknown"),
                "user": (i.get("user") or {}).get("login"),
                "labels": [lab.get("name") for lab in i.get("labels") or [] if lab.get("name")],
                "created_at": i.get("created_at"),
                "url": i.get("html_url", ""),
            }
            for i in data
            if "pull_request" not in i
        ]
        return ActivityResult(True, items=items)

    def list_workflow_runs(self, ref: GitHubRepoRef, limit: int = 10) -> ActivityResult:
        try:
            data = self._request(
                f"/repos/{ref.owner}/{ref.repo}/actions/runs", params={"per_page": limit}
            )
        except (UpstreamError, NotFoundError) as exc:
            return ActivityResult(False, exc.message)
        items = [
            {
                "id": run.get("id"),
                "name": run.get("name"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "branch": run.get("head_branch"),
                "created_at": run.get("created_at"),
                "url": run.get("html_url", ""),
            }
            for run in (data.get("workflow_runs") or [])
        ]
        return ActivityResult(True, items=items)


def decode_content_payload(payload: dict[str, Any]) -> str | None:
    """Decode the contents API's base64 body. Kept for adapters that use that endpoint."""
    content = payload.get("content")
    if not isinstance(content, str):
        return None
    try:
        raw = base64.b64decode(content)
        return raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
