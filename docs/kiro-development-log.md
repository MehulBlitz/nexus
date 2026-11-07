# Kiro development log

Only real, evidenced activity is recorded here. This project was authored in a coding environment
without the Kiro IDE, so files were created directly in the repository; running Kiro agents, hooks or
the Kiro MCP client is explicitly **not** claimed.

## Implemented as committed files

- Steering: `product.md`, `architecture.md`, `coding-standards.md`, `security.md`, `testing.md`.
- Custom agent definitions: architecture-reviewer, security-reviewer, test-engineer,
  documentation-engineer.
- Foundation spec: requirements, design, tasks.
- Feature specs: authentication, repository-ingestion, code-intelligence, knowledge-graph,
  risk-analysis, multi-agent, investigation, github-integration, mcp-server, frontend,
  deployment-security. Each records requirements, acceptance criteria, design, data/API contracts,
  tasks and tests.
- Hook proposal: `.kiro/hooks/README.md`.

## Decisions shaped by specs

- Evidence policy: every hypothesis needs at least one file reference; orchestrator verifies paths.
- Missing risk signals are excluded and weights renormalised; scores are not probabilities.
- Parser choice recorded honestly: Python AST, lexer for JS/TS/Java.
- Durable database job queue instead of Redis/RQ, documented as a deviation.
- MCP defaults to read-only; the two write-capable tools require an explicit opt-in.

## Not done (requires a real Kiro session)

- Running spec tasks through Kiro.
- Installing/approving hooks in the Kiro UI (only a proposal is committed).
- Connecting Kiro to the NEXUS MCP server.
- Screenshots of Kiro using NEXUS tools.
- Any claim that Kiro executed tests or generated code.

## Verification

- `BUILD_STATUS.md` records what was tested and what remains blocked.
- MCP unit tests pass; a live Kiro tool call is still required for the Kiro/MCP acceptance item.
