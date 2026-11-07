"""NEXUS MCP stdio server.

Run with:

    NEXUS_API_URL=http://localhost:8000 \
    NEXUS_API_TOKEN=<personal API token> \
    python -m nexus_mcp.server

Writes are disabled unless NEXUS_MCP_ALLOW_WRITES=1.
"""

from __future__ import annotations

import os
from typing import Any

try:  # MCP SDK 1.x
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("nexus")
except ModuleNotFoundError:  # MCP SDK 2.x renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("nexus")

from nexus_mcp import tools
from nexus_mcp.client import NexusApiError, NexusClient


def get_client() -> NexusClient:
    base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")
    token = os.environ.get("NEXUS_API_TOKEN", "").strip()
    if not token:
        raise NexusApiError(
            "NEXUS_API_TOKEN is not set. Create a personal API token in NEXUS Settings."
        )
    return NexusClient(base_url, token, timeout=float(os.environ.get("NEXUS_MCP_TIMEOUT", "20")))


def writes_allowed() -> bool:
    return os.environ.get("NEXUS_MCP_ALLOW_WRITES", "").strip().lower() in {"1", "true", "yes"}


@mcp.tool()
def get_repository_overview(repository_id: str) -> dict[str, Any]:
    """Return repository metadata, language distribution, modules and the latest snapshot.

    Args:
        repository_id: NEXUS repository UUID.
    """
    return tools.repository_overview(get_client(), repository_id)


@mcp.tool()
def search_code(
    repository_id: str,
    search_query: str,
    language: str | None = None,
    directory: str | None = None,
) -> dict[str, Any]:
    """Search indexed paths and symbols plus source content at the indexed commit.

    Args:
        repository_id: NEXUS repository UUID.
        search_query: Text to find (at least two characters).
        language: Optional language filter, for example Python.
        directory: Optional path prefix filter.
    """
    return tools.search_code(get_client(), repository_id, search_query, language, directory)


@mcp.tool()
def get_dependency_chain(
    repository_id: str,
    node: str,
    direction: str = "dependencies",
    max_depth: int = 3,
) -> dict[str, Any]:
    """Traverse the dependency graph from a node id, file path or exact symbol name.

    Args:
        repository_id: NEXUS repository UUID.
        node: Node id, file path, or symbol name.
        direction: "dependencies" (outgoing) or "dependents" (incoming).
        max_depth: Traversal depth, 1-8.
    """
    return tools.dependency_chain(get_client(), repository_id, node, direction, max_depth)


@mcp.tool()
def analyze_release_risk(repository_id: str, branch: str | None = None) -> dict[str, Any]:
    """Return the latest evidence-backed risk summary and findings for the indexed snapshot.

    Args:
        repository_id: NEXUS repository UUID.
        branch: Optional branch label; analysis remains snapshot-scoped.
    """
    return tools.analyze_release_risk(get_client(), repository_id, branch)


@mcp.tool()
def investigate_issue(repository_id: str, question: str) -> dict[str, Any]:
    """Investigate a question with NEXUS agents, or return an existing completed investigation.

    Creating a new investigation requires NEXUS_MCP_ALLOW_WRITES=1 on the server.

    Args:
        repository_id: NEXUS repository UUID.
        question: Developer question, at least 8 characters.
    """
    return tools.investigate_issue(get_client(), repository_id, question, writes_allowed())


@mcp.tool()
def get_agent_status(investigation_id: str) -> dict[str, Any]:
    """Return investigation status, agent runs, outputs and errors.

    Args:
        investigation_id: NEXUS investigation UUID.
    """
    return tools.get_agent_status(get_client(), investigation_id)


@mcp.tool()
def generate_release_report(
    repository_id: str, snapshot: str | None = None, title: str | None = None
) -> dict[str, Any]:
    """Generate (or return the latest) Markdown engineering report.

    Creating a report requires NEXUS_MCP_ALLOW_WRITES=1 on the server.

    Args:
        repository_id: NEXUS repository UUID.
        snapshot: Optional snapshot id; reports use the latest indexed snapshot.
        title: Optional report title.
    """
    return tools.generate_release_report(
        get_client(), repository_id, snapshot, writes_allowed(), title
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
