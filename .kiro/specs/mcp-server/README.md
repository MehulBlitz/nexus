# MCP server spec

Status: IMPLEMENTED · TESTED (unit tests with a mocked transport). Not yet exercised against a live
Kiro client in this environment.

## Requirements

1. Run as a separate process from the backend and communicate over MCP stdio.
2. Authenticate every backend request with a personal API token (bearer).
3. Reuse backend endpoints; do not duplicate analysis or read the database.
4. Expose seven tools: repository overview, code search, dependency chain, release risk,
   investigation, agent status, release report.
5. Validate arguments before issuing a request; reject unknown direction/depth values.
6. Return readable errors without leaking tokens.
7. Keep destructive operations impossible; default to read-only.
8. Document client configuration and provide tests for each tool.

## Acceptance criteria

- [x] All seven tools are registered.
- [x] Bearer token is sent and never appears in errors.
- [x] A file path or symbol name resolves to a graph node before traversal.
- [x] Invalid direction/depth is rejected before a network call.
- [x] Write-capable tools are disabled unless `NEXUS_MCP_ALLOW_WRITES=1`.
- [x] API errors map to `NexusApiError` with status and message.
- [x] `httpx.MockTransport` tests cover request construction and gating.
- [ ] A real Kiro session calls at least two tools (requires Kiro UI; not performed here).

## Design

```text
MCP client ──stdio──> nexus_mcp.server (FastMCP/MCPServer)
                              │
                              ├── tools.py (argument validation, shaping)
                              └── client.py (httpx, bearer auth, timeouts)
                                        │
                                        v
                              NEXUS FastAPI /api/v1
```

- `get_dependency_chain` resolves the supplied id/path/name through the graph search endpoint.
- `investigate_issue` first looks for an existing completed investigation with the same question.
- `generate_release_report` returns the latest report when writes are disabled.
- Risk analysis remains backend-triggered; the tool reads the latest summary.

## Tools and API contracts

| Tool | Backend call | Writes |
|---|---|---|
| `get_repository_overview` | `GET /repositories/{id}/overview` | no |
| `search_code` | `GET /repositories/{id}/search?q=&language=&directory=` | no |
| `get_dependency_chain` | `GET /repositories/{id}/graph?search=` then `/graph/dependencies/{node}` | no |
| `analyze_release_risk` | `GET /repositories/{id}/risks/summary` (+ findings) | no |
| `investigate_issue` | `GET .../investigations` or `POST .../investigations` | opt-in |
| `get_agent_status` | `GET /investigations/{id}` | no |
| `generate_release_report` | `GET .../reports` + `/reports/{id}` or `POST .../reports` | opt-in |

## Data models

Responses are plain JSON shaped for model consumption: node summaries include id, type, file path,
line range, language and degrees; traversal steps include edge relationship, confidence and origin.

## Tasks

- [x] Package scaffold and console entry point.
- [x] Bearer client with timeout and error mapping.
- [x] Seven tool functions.
- [x] Argument validation and write gating.
- [x] Unit tests.
- [x] Setup documentation.
- [ ] Live Kiro MCP connection and screenshot evidence.

## Test requirements

- Unit: URL, auth header, error message, validation, write gating, report fallback.
- Unit: all seven tools registered.
- Integration (not run): call each tool against a running backend with a real token.
