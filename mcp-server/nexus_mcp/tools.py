"""The seven NEXUS MCP tools.

Six are read-only. ``investigate_issue`` and ``generate_release_report`` create records, so they are
disabled unless the operator explicitly sets ``NEXUS_MCP_ALLOW_WRITES=1``; without it they return
an existing result or a clear explanation instead of pretending to run.
"""

from __future__ import annotations

from typing import Any

from nexus_mcp.client import NexusApiError, NexusClient

WRITE_DISABLED = (
    "This tool creates a NEXUS record, so it is disabled in read-only mode. "
    "Set NEXUS_MCP_ALLOW_WRITES=1 in the MCP server environment to enable it."
)


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "qualified_name": node.get("qualified_name"),
        "node_type": node.get("node_type"),
        "file_path": node.get("file_path"),
        "start_line": node.get("start_line"),
        "end_line": node.get("end_line"),
        "language": node.get("language"),
        "in_degree": node.get("in_degree"),
        "out_degree": node.get("out_degree"),
    }


def resolve_node(client: NexusClient, repository_id: str, identifier: str) -> dict[str, Any]:
    """Resolve a node id, file path, or exact symbol name to a graph node."""
    identifier = _require_text(identifier, "node")
    view = client.get(
        f"/api/v1/repositories/{repository_id}/graph",
        params={"search": identifier[:200], "limit": 200},
    )
    nodes = view.get("nodes", [])
    for node in nodes:
        if node.get("id") == identifier:
            return node
    for node in nodes:
        if node.get("file_path") == identifier:
            return node
    for node in nodes:
        if node.get("qualified_name") == identifier or node.get("name") == identifier:
            return node
    for node in nodes:
        if identifier.lower() in (node.get("qualified_name") or node.get("name") or "").lower():
            return node
    raise ValueError(f"No graph node matched {identifier!r} in this repository")


def repository_overview(client: NexusClient, repository_id: str) -> dict[str, Any]:
    repository_id = _require_text(repository_id, "repository_id")
    overview = client.get(f"/api/v1/repositories/{repository_id}/overview")
    snapshot = overview.get("snapshot") or {}
    return {
        "repository": {
            "id": overview["repository"]["id"],
            "full_name": overview["repository"]["full_name"],
            "description": overview["repository"].get("description"),
            "default_branch": overview["repository"].get("default_branch"),
            "status": overview["repository"].get("status"),
            "html_url": overview["repository"].get("html_url"),
        },
        "snapshot": {
            "id": snapshot.get("id"),
            "commit_sha": snapshot.get("commit_sha"),
            "branch": snapshot.get("branch"),
            "file_count": snapshot.get("file_count"),
            "symbol_count": snapshot.get("symbol_count"),
            "edge_count": snapshot.get("edge_count"),
            "created_at": snapshot.get("created_at"),
        }
        if snapshot
        else None,
        "languages": overview.get("languages", []),
        "file_count": overview.get("file_count"),
        "symbol_count": overview.get("symbol_count"),
        "module_count": overview.get("module_count"),
        "test_file_count": overview.get("test_file_count"),
        "top_modules": overview.get("top_modules", []),
        "entry_points": overview.get("entry_points", []),
        "parser_coverage": overview.get("parser_coverage", {}),
        "warnings": overview.get("warnings", []),
        "limitations": [
            "Static analysis only; imported source code is never executed.",
            "Lexer languages report declarations they could match, not full semantics.",
        ],
    }


def search_code(
    client: NexusClient,
    repository_id: str,
    search_query: str,
    language: str | None = None,
    directory: str | None = None,
) -> dict[str, Any]:
    repository_id = _require_text(repository_id, "repository_id")
    search_query = _require_text(search_query, "search_query")
    params: dict[str, Any] = {"q": search_query[:200]}
    if language:
        params["language"] = language
    if directory:
        params["directory"] = directory
    hits = client.get(f"/api/v1/repositories/{repository_id}/search", params=params)
    return {
        "query": search_query,
        "count": len(hits),
        "results": hits[:50],
        "note": "Content hits fetch the file from GitHub at the indexed commit; files are not stored.",
    }


def dependency_chain(
    client: NexusClient,
    repository_id: str,
    node: str,
    direction: str = "dependencies",
    max_depth: int = 3,
) -> dict[str, Any]:
    repository_id = _require_text(repository_id, "repository_id")
    if direction not in {"dependencies", "dependents"}:
        raise ValueError("direction must be 'dependencies' or 'dependents'")
    if not isinstance(max_depth, int) or not 1 <= max_depth <= 8:
        raise ValueError("max_depth must be an integer between 1 and 8")
    root = resolve_node(client, repository_id, node)
    chain = client.get(
        f"/api/v1/repositories/{repository_id}/graph/dependencies/{root['id']}",
        params={"direction": direction, "max_depth": max_depth},
    )
    return {
        "root": _node_summary(chain["root"]),
        "direction": chain["direction"],
        "max_depth": chain["max_depth"],
        "truncated": chain["truncated"],
        "explanation": chain["explanation"],
        "steps": [
            {
                "node": _node_summary(step["node"]),
                "depth": step["depth"],
                "relationship": (step.get("via_edge") or {}).get("relationship_type"),
                "confidence": (step.get("via_edge") or {}).get("confidence"),
                "origin": (step.get("via_edge") or {}).get("origin"),
                "path": step.get("path", []),
            }
            for step in chain["steps"]
        ],
    }


def analyze_release_risk(client: NexusClient, repository_id: str, branch: str | None = None) -> dict[str, Any]:
    repository_id = _require_text(repository_id, "repository_id")
    summary = client.get(f"/api/v1/repositories/{repository_id}/risks/summary")
    findings = (
        client.get(f"/api/v1/repositories/{repository_id}/risks")
        if summary.get("analysis_run_id")
        else []
    )
    return {
        "repository_id": repository_id,
        "branch_requested": branch,
        "snapshot_id": summary.get("snapshot_id"),
        "analysis_run_id": summary.get("analysis_run_id"),
        "overall_score": summary.get("overall_score"),
        "overall_severity": summary.get("overall_severity"),
        "confidence": summary.get("confidence"),
        "severity_counts": summary.get("severity_counts", {}),
        "signals_available": summary.get("signals_available", []),
        "signals_unavailable": summary.get("signals_unavailable", []),
        "limitations": summary.get("limitations", []),
        "findings": findings[:20],
        "note": (
            "Risk scores are prioritisation heuristics, not failure probabilities. "
            "If no analysis exists, run one from the NEXUS UI or POST /risks/analyze."
        ),
        "branch_note": (
            "Analysis is snapshot-scoped; the NEXUS backend analyses the latest indexed commit."
            if branch
            else None
        ),
    }


def investigate_issue(
    client: NexusClient,
    repository_id: str,
    question: str,
    allow_writes: bool = False,
) -> dict[str, Any]:
    repository_id = _require_text(repository_id, "repository_id")
    question = _require_text(question, "question")
    if len(question) < 8:
        raise ValueError("question must be at least 8 characters")
    if not allow_writes:
        existing = client.get(f"/api/v1/repositories/{repository_id}/investigations")
        for item in existing.get("items", []):
            if item.get("question") == question and item.get("status") == "completed":
                detail = client.get(f"/api/v1/investigations/{item['id']}")
                return {"mode": "existing", **detail}
        return {"mode": "disabled", "message": WRITE_DISABLED}
    created = client.post(
        f"/api/v1/repositories/{repository_id}/investigations", json={"question": question}
    )
    return {
        "mode": "created",
        "investigation": created,
        "note": "Investigation queued. Poll get_agent_status with the investigation id.",
    }


def get_agent_status(client: NexusClient, investigation_id: str, allow_writes: bool = False) -> dict[str, Any]:
    del allow_writes  # read-only regardless of the write flag
    investigation_id = _require_text(investigation_id, "investigation_id")
    detail = client.get(f"/api/v1/investigations/{investigation_id}")
    result = detail.get("result") or {}
    return {
        "investigation_id": detail["id"],
        "status": detail["status"],
        "progress": detail["progress"],
        "question": detail["question"],
        "ai_used": detail["ai_used"],
        "error_message": detail.get("error_message"),
        "summary": detail.get("summary"),
        "agent_runs": [
            {
                "agent": run["agent_name"],
                "status": run["status"],
                "execution_time": run.get("execution_time"),
                "error": run.get("error_message"),
            }
            for run in detail.get("agent_runs", [])
        ],
        "agent_status": result.get("agent_status", []),
        "limitations": result.get("limitations", []),
    }


def generate_release_report(
    client: NexusClient,
    repository_id: str,
    snapshot: str | None = None,
    allow_writes: bool = False,
    title: str | None = None,
) -> dict[str, Any]:
    repository_id = _require_text(repository_id, "repository_id")
    if not allow_writes:
        reports = client.get(f"/api/v1/repositories/{repository_id}/reports")
        items = reports.get("items", [])
        if items:
            latest = client.get(f"/api/v1/reports/{items[0]['id']}")
            return {"mode": "existing", "report": latest}
        return {"mode": "disabled", "message": WRITE_DISABLED}
    created = client.post(
        f"/api/v1/repositories/{repository_id}/reports",
        json={"title": title, "investigation_id": None},
    )
    return {
        "mode": "created",
        "report": {
            "id": created["id"],
            "title": created["title"],
            "created_at": created["created_at"],
            "snapshot_requested": snapshot,
            "markdown": created["markdown"],
        },
    }


TOOL_FUNCTIONS = {
    "get_repository_overview": repository_overview,
    "search_code": search_code,
    "get_dependency_chain": dependency_chain,
    "analyze_release_risk": analyze_release_risk,
    "investigate_issue": investigate_issue,
    "get_agent_status": get_agent_status,
    "generate_release_report": generate_release_report,
}

__all__ = [
    "TOOL_FUNCTIONS",
    "NexusApiError",
    "analyze_release_risk",
    "dependency_chain",
    "generate_release_report",
    "get_agent_status",
    "investigate_issue",
    "repository_overview",
    "resolve_node",
    "search_code",
]
