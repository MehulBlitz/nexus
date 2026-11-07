# NEXUS MCP server

Read-only-by-default access to NEXUS repository intelligence from any MCP client (Kiro, Claude
Desktop, or the MCP inspector).

The server is a thin authenticated HTTP client. It calls the same `/api/v1` endpoints as the web
application, so ownership checks, authorisation and analysis logic are not duplicated.

## Requirements

- NEXUS backend running and reachable
- A personal API token from **NEXUS → Settings → API tokens**
- Python 3.11+

```bash
cd mcp-server
pip install .
```

## Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `NEXUS_API_URL` | no | `http://localhost:8000` | Backend origin |
| `NEXUS_API_TOKEN` | **yes** | — | Personal API token, sent as a bearer token |
| `NEXUS_MCP_ALLOW_WRITES` | no | unset | `1` enables creating investigations and reports |
| `NEXUS_MCP_TIMEOUT` | no | `20` | Per-request timeout in seconds |

The token is never logged or returned. Nothing is read from the database directly.

## Run

```bash
NEXUS_API_URL=http://localhost:8000 \
NEXUS_API_TOKEN="$NEXUS_TOKEN" \
python -m nexus_mcp.server
```

The server speaks MCP over stdio. Example client configuration:

```json
{
  "mcpServers": {
    "nexus": {
      "command": "python",
      "args": ["-m", "nexus_mcp.server"],
      "env": {
        "NEXUS_API_URL": "http://localhost:8000",
        "NEXUS_API_TOKEN": "paste-your-token-here"
      }
    }
  }
}
```

For Kiro, add the equivalent entry to the MCP configuration and keep the token in the local
environment; do not commit it.

## Tools

| Tool | Read-only | Returns |
|---|---|---|
| `get_repository_overview` | yes | Metadata, languages, modules, snapshot, parser warnings |
| `search_code` | yes | Path/symbol/content hits with line numbers |
| `get_dependency_chain` | yes | Bounded traversal, edge type, confidence and origin |
| `analyze_release_risk` | yes | Latest weighted risk summary and findings |
| `investigate_issue` | opt-in | Existing completed investigation, or a queued one when writes are enabled |
| `get_agent_status` | yes | Agent runs, statuses, timings, errors, limitations |
| `generate_release_report` | opt-in | Latest report, or a newly generated Markdown report when writes are enabled |

Without `NEXUS_MCP_ALLOW_WRITES=1`, the two write-capable tools never mutate state: they return an
existing completed record or a message explaining that writes are disabled. This keeps the default
configuration read-only.

## Tests

```bash
cd mcp-server
PYTHONPATH=. python -m pytest -q
python -m ruff check .
```

Tests use an `httpx.MockTransport`; they verify bearer authentication, error mapping, URL
construction, node resolution, write gating and tool registration. They do not require a running
backend.

## Limitations

- Risk analysis and indexing are triggered by the backend; the MCP server does not run them.
- `branch` on `analyze_release_risk` is a label only; analysis is snapshot-scoped.
- `search_code` content matches require the backend to fetch the file from GitHub at the indexed
  commit, subject to GitHub rate limits.
- Tools are not streamed; an investigation in progress returns its current status.
