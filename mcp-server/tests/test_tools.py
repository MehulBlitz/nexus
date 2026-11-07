from __future__ import annotations

import json

import httpx
import pytest

from nexus_mcp import tools
from nexus_mcp.client import NexusApiError, NexusClient


def make_client(handler) -> NexusClient:
    return NexusClient("http://nexus.test", "test-token", transport=httpx.MockTransport(handler))


def test_client_sends_bearer_token_and_parses_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    assert client.get("/api/v1/repositories/abc/overview") == {"ok": True}
    assert seen["auth"] == "Bearer test-token"
    assert seen["url"] == "http://nexus.test/api/v1/repositories/abc/overview"


def test_client_maps_api_error_without_leaking_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": {"code": "forbidden", "message": "You do not own this repository"}},
        )

    with pytest.raises(NexusApiError) as exc:
        make_client(handler).get("/api/v1/repositories/abc")
    assert exc.value.status == 403
    assert "do not own" in str(exc.value)
    assert "test-token" not in str(exc.value)


def test_client_rejects_invalid_base_url_and_missing_token():
    with pytest.raises(ValueError):
        NexusClient("file:///etc/passwd", "token")
    with pytest.raises(ValueError):
        NexusClient("http://localhost:8000", "")


def test_repository_overview_summarises_snapshot():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/overview")
        return httpx.Response(
            200,
            json={
                "repository": {
                    "id": "r1",
                    "full_name": "acme/demo",
                    "description": "demo",
                    "default_branch": "main",
                    "status": "indexed",
                    "html_url": "https://github.com/acme/demo",
                },
                "snapshot": {
                    "id": "s1",
                    "commit_sha": "a" * 40,
                    "branch": "main",
                    "file_count": 6,
                    "symbol_count": 12,
                    "edge_count": 9,
                    "created_at": "2026-01-01T00:00:00Z",
                },
                "languages": [{"language": "Python", "files": 4, "symbols": 9, "percent": 66.7}],
                "file_count": 6,
                "symbol_count": 12,
                "module_count": 3,
                "test_file_count": 1,
                "top_modules": [],
                "entry_points": ["app/main.py"],
                "parser_coverage": {"parse_modes": {"ast": 4}},
                "warnings": ["app/broken.py: syntax error"],
            },
        )

    result = tools.repository_overview(make_client(handler), "r1")
    assert result["repository"]["full_name"] == "acme/demo"
    assert result["snapshot"]["commit_sha"] == "a" * 40
    assert result["languages"][0]["language"] == "Python"
    assert result["warnings"]


def test_dependency_chain_resolves_a_file_path_first():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/graph"):
            assert request.url.params["search"] == "app/auth.py"
            return httpx.Response(
                200,
                json={
                    "nodes": [
                        {
                            "id": "n1",
                            "name": "auth.py",
                            "qualified_name": "app.auth",
                            "node_type": "file",
                            "file_path": "app/auth.py",
                            "start_line": 1,
                            "end_line": 40,
                            "language": "Python",
                            "in_degree": 2,
                            "out_degree": 1,
                        }
                    ]
                },
            )
        if "/graph/dependencies/n1" in request.url.path:
            assert request.url.params["direction"] == "dependents"
            assert request.url.params["max_depth"] == "2"
            return httpx.Response(
                200,
                json={
                    "root": {
                        "id": "n1",
                        "name": "auth.py",
                        "qualified_name": "app.auth",
                        "node_type": "file",
                        "file_path": "app/auth.py",
                        "start_line": 1,
                        "end_line": 40,
                        "language": "Python",
                        "in_degree": 2,
                        "out_degree": 1,
                    },
                    "direction": "dependents",
                    "max_depth": 2,
                    "steps": [
                        {
                            "node": {
                                "id": "n2",
                                "name": "test_auth.py",
                                "node_type": "test",
                                "file_path": "tests/test_auth.py",
                                "in_degree": 0,
                                "out_degree": 1,
                            },
                            "depth": 1,
                            "via_edge": {
                                "relationship_type": "TESTS",
                                "confidence": 1.0,
                                "origin": "parsed",
                            },
                            "path": ["auth.py"],
                        }
                    ],
                    "truncated": False,
                    "explanation": "bounded BFS",
                },
            )
        raise AssertionError(request.url)

    result = tools.dependency_chain(make_client(handler), "r1", "app/auth.py", "dependents", 2)
    assert result["root"]["id"] == "n1"
    assert result["steps"][0]["relationship"] == "TESTS"
    assert result["steps"][0]["confidence"] == 1.0
    assert len(calls) == 2


def test_dependency_chain_validates_direction_and_depth():
    client = make_client(lambda request: httpx.Response(500))
    with pytest.raises(ValueError):
        tools.dependency_chain(client, "r1", "a.py", "sideways", 2)
    with pytest.raises(ValueError):
        tools.dependency_chain(client, "r1", "a.py", "dependencies", 99)


def test_investigate_is_disabled_without_opt_in():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/investigations"):
            return httpx.Response(200, json={"items": []})
        raise AssertionError(request.url)

    result = tools.investigate_issue(make_client(handler), "r1", "Why does login fail?", False)
    assert result["mode"] == "disabled"
    assert "NEXUS_MCP_ALLOW_WRITES" in result["message"]


def test_investigate_creates_when_writes_are_enabled():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert json.loads(request.content)["question"] == "Why does login fail?"
        return httpx.Response(
            202,
            json={"id": "i1", "status": "queued", "question": "Why does login fail?"},
        )

    result = tools.investigate_issue(make_client(handler), "r1", "Why does login fail?", True)
    assert result["mode"] == "created"
    assert result["investigation"]["id"] == "i1"


def test_agent_status_reports_runs_and_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "i1",
                "status": "completed",
                "progress": 100,
                "question": "Why?",
                "ai_used": False,
                "error_message": None,
                "summary": "Evidence-backed summary",
                "agent_runs": [
                    {
                        "agent_name": "bug_investigator",
                        "status": "completed",
                        "execution_time": 0.4,
                        "error_message": None,
                    }
                ],
                "result": {"limitations": ["No LLM configured"]},
            },
        )

    result = tools.get_agent_status(make_client(handler), "i1")
    assert result["status"] == "completed"
    assert result["agent_runs"][0]["agent"] == "bug_investigator"
    assert result["limitations"] == ["No LLM configured"]


def test_generate_report_returns_latest_without_writes():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/reports"):
            return httpx.Response(200, json={"items": [{"id": "rep1"}]})
        if request.url.path.endswith("/reports/rep1"):
            return httpx.Response(
                200, json={"id": "rep1", "title": "Release review", "markdown": "# Report"}
            )
        raise AssertionError(request.url)

    result = tools.generate_release_report(make_client(handler), "r1", None, False)
    assert result["mode"] == "existing"
    assert result["report"]["markdown"] == "# Report"


def test_server_exposes_all_seven_tools():
    import asyncio

    from nexus_mcp.server import mcp

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert names == set(tools.TOOL_FUNCTIONS)
