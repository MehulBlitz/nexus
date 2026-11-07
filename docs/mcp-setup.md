# MCP setup

The NEXUS MCP server exposes repository intelligence to MCP clients. It is a separate process that
calls the authenticated backend API; it never reads the database.

Full package documentation: [`mcp-server/README.md`](../mcp-server/README.md).

## 1. Start NEXUS

```bash
cd backend && uvicorn app.main:app --port 8000
```

## 2. Create a personal API token

Register and sign in, then open **Settings → API tokens → Create**. Copy the token immediately; only
a hash is stored. Do not paste it into source control or chat.

## 3. Install and run the server

```bash
cd mcp-server
pip install .
NEXUS_API_URL=http://localhost:8000 \
NEXUS_API_TOKEN="$NEXUS_TOKEN" \
python -m nexus_mcp.server
```

The transport is stdio.

## 4. Client configuration

Kiro or Claude Desktop style:

```json
{
  "mcpServers": {
    "nexus": {
      "command": "python",
      "args": ["-m", "nexus_mcp.server"],
      "env": {
        "NEXUS_API_URL": "http://localhost:8000",
        "NEXUS_API_TOKEN": "paste-token-here",
        "NEXUS_MCP_ALLOW_WRITES": "0"
      }
    }
  }
}
```

Keep the token in a local environment variable or the client's secret store. The committed repo
contains no credentials.

## 5. Tools

`get_repository_overview`, `search_code`, `get_dependency_chain`, `analyze_release_risk`,
`investigate_issue`, `get_agent_status`, `generate_release_report`.

Example prompts once connected:

- "Use NEXUS get_repository_overview for repository `<id>` and summarise the languages and parser warnings."
- "Use NEXUS get_dependency_chain for `app/auth.py`, direction dependents, depth 3."
- "Use NEXUS analyze_release_risk and list the evidence behind the highest finding."
- "Use NEXUS investigate_issue to ask why session refresh loses authentication."

## Write gating

`investigate_issue` and `generate_release_report` create records, so they are disabled unless
`NEXUS_MCP_ALLOW_WRITES=1`. Without it they return an existing completed result or a clear message.
All other tools are read-only.

## Verification status

- Unit tests (mocked transport): 11 passing.
- Live MCP calls from Kiro: **verified** against the indexed `MehulBlitz/nexus` repository.
  All seven tools completed successfully, including investigation polling and Markdown report
  generation.

## Free Kiro verification steps

1. Start the local Compose stack with `docker compose up -d`.
2. Register a local user, open **Settings → API tokens**, and create a token.
3. Add the JSON configuration above to Kiro's MCP configuration. Use the absolute path to the
   repository's Python executable if `python` is not on Kiro's PATH.
4. Reload Kiro MCP servers and run `get_repository_overview` against the imported repository.
5. Run one read-only search tool, capture the tool result, and update `BUILD_STATUS.md`.
6. Keep `NEXUS_MCP_ALLOW_WRITES=0` unless explicitly testing investigation/report writes.
