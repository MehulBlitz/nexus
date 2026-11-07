"""A small, realistic public repository served by httpx.MockTransport for tests.

No network access is used, and no repository code is executed.
"""

from __future__ import annotations

import httpx

SHA = "a" * 40
OWNER = "acme"
REPO = "demo"
COMMIT_DATE = "2026-10-30T12:00:00Z"

FILES: dict[str, str] = {
    "app/__init__.py": '"""Demo application."""\n',
    "app/auth.py": '''"""Authentication helpers."""
from app.session import load_session


def refresh_session(token: str):
    if not token:
        return None
    session = load_session(token)
    return session
''',
    "app/session.py": '''"""In-memory session store used by the demo."""
CACHE: dict[str, str] = {}


def load_session(token: str):
    return CACHE.get(token)


def save_session(token: str, value: str):
    CACHE[token] = value
    return value
''',
    "app/api/__init__.py": "",
    "app/api/routes.py": '''"""HTTP routes."""
from fastapi import APIRouter

from app.auth import refresh_session

router = APIRouter()


@router.post("/refresh")
def refresh(token: str):
    return refresh_session(token)
''',
    "app/broken.py": "def broken(:\n    return 1\n",
    "tests/test_auth.py": '''from app.auth import refresh_session


def test_refresh_returns_none_for_empty_token():
    assert refresh_session("") is None
''',
    "lib/api.ts": """export const api = {
  get: async (path: string) => fetch(path),
};
""",
    "web/store.ts": """import { api } from "../lib/api";

export class SessionStore {
  load() {
    return api.get("/session");
  }
}
""",
}


def repository_metadata() -> dict:
    return {
        "id": 424242,
        "name": REPO,
        "full_name": f"{OWNER}/{REPO}",
        "html_url": f"https://github.com/{OWNER}/{REPO}",
        "description": "Demo repository for NEXUS tests",
        "default_branch": "main",
        "visibility": "public",
        "private": False,
        "language": "Python",
        "stargazers_count": 3,
        "size": 64,
    }


def _tree() -> dict:
    blobs = []
    for path, content in FILES.items():
        blobs.append(
            {"type": "blob", "path": path, "sha": "b" * 40, "size": len(content.encode("utf-8"))}
        )
    blobs.append({"type": "tree", "path": "app", "sha": "c" * 40})
    return {"sha": SHA, "truncated": False, "tree": blobs}


def handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    path = request.url.path
    if host == "raw.githubusercontent.com":
        parts = path.lstrip("/").split("/")
        file_path = "/".join(parts[3:])
        content = FILES.get(file_path)
        if content is None:
            return httpx.Response(404)
        return httpx.Response(200, content=content.encode("utf-8"))

    if path == f"/repos/{OWNER}/{REPO}":
        return httpx.Response(200, json=repository_metadata())
    if path == f"/repos/{OWNER}/{REPO}/branches/main":
        return httpx.Response(200, json={"name": "main", "commit": {"sha": SHA}})
    if path == f"/repos/{OWNER}/{REPO}/git/trees/{SHA}":
        return httpx.Response(200, json=_tree())
    if path == f"/repos/{OWNER}/{REPO}/commits":
        return httpx.Response(
            200,
            json=[
                {
                    "sha": SHA,
                    "html_url": f"https://github.com/{OWNER}/{REPO}/commit/{SHA}",
                    "commit": {
                        "message": "Refactor authentication refresh",
                        "author": {"name": "Demo Author", "date": COMMIT_DATE},
                    },
                }
            ],
        )
    if path.startswith(f"/repos/{OWNER}/{REPO}/commits/"):
        return httpx.Response(
            200,
            json={
                "sha": SHA,
                "commit": {
                    "message": "Refactor authentication refresh",
                    "author": {"name": "Demo Author", "date": COMMIT_DATE},
                },
                "files": [
                    {"filename": "app/auth.py"},
                    {"filename": "app/session.py"},
                ],
            },
        )
    if path == f"/repos/{OWNER}/{REPO}/pulls":
        return httpx.Response(
            200,
            json=[
                {
                    "number": 7,
                    "title": "Harden refresh flow",
                    "state": "open",
                    "user": {"login": "demo"},
                    "created_at": COMMIT_DATE,
                    "updated_at": COMMIT_DATE,
                    "html_url": f"https://github.com/{OWNER}/{REPO}/pull/7",
                    "draft": False,
                }
            ],
        )
    if path == f"/repos/{OWNER}/{REPO}/issues":
        return httpx.Response(
            200,
            json=[
                {
                    "number": 9,
                    "title": "Refresh loses session",
                    "state": "open",
                    "user": {"login": "reporter"},
                    "labels": [{"name": "bug"}],
                    "created_at": COMMIT_DATE,
                    "html_url": f"https://github.com/{OWNER}/{REPO}/issues/9",
                }
            ],
        )
    if path == f"/repos/{OWNER}/{REPO}/actions/runs":
        return httpx.Response(403)  # workflows are restricted for this repository
    return httpx.Response(404)


def make_client() -> httpx.Client:
    raise NotImplementedError("Use app.integrations.github.GitHubClient with make_transport()")


def make_transport() -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def build_test_client():
    from app.integrations.github import GitHubClient

    return GitHubClient(
        api_base="https://api.github.com",
        raw_base="https://raw.githubusercontent.com",
        max_retries=0,
        timeout_seconds=2,
        transport=make_transport(),
        sleep=lambda _s: None,
    )
