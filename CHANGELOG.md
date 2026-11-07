# Changelog

## Unreleased — Core Release 1

### Added

- Authentication: registration, login, refresh, logout, password change, account deletion, personal
  API tokens, Argon2id hashing, HttpOnly sessions, CSRF double-submit, rate limits, audit events.
- 16 SQLAlchemy models and an initial Alembic migration with indexes and cascades.
- GitHub adapter with strict URL parsing, tree/raw fetch, retries, rate-limit mapping, activity cache.
- Public repository import, snapshot creation, durable indexing jobs, progress and failure states.
- Python AST analyzer and documented lexer for JavaScript, TypeScript and Java; parser warnings and
  coverage reporting.
- Knowledge graph builder and bounded engine: traversal, reverse traversal, cycles, components,
  centrality, impact analysis, evidence and confidence.
- Transparent risk engine with five signals, renormalisation, thresholds, evidence-backed findings and
  recommendations.
- Five specialised agents, strict output schemas, optional Ollama/OpenAI-compatible provider,
  deterministic fallback, orchestrator with parallelism, timeouts, evidence verification and partial
  failure handling.
- Investigations with SSE/polling, agent timeline, hypotheses, review plan, cancellation and history.
- Reports with Markdown export.
- MCP server with seven tools, bearer authentication, node resolution, validation and write gating.
- Full React UI: landing, auth, dashboard, repositories, overview, graph explorer, risk center,
  investigations, agents, reports, settings, loading/empty/error states.
- Kiro steering, 12 specs, four custom agent definitions and a hook proposal.
- Documentation: architecture, API, security, deployment, MCP, user guide, demo script, Kiro log.
- CI and security workflow definitions; Dockerfiles for backend, frontend and MCP; Compose stack.
- Tests: 115 backend, 9 frontend, 11 MCP, plus Hypothesis graph/risk properties.

### Changed

- Frontend upgraded to React Router, TanStack Query, Zustand, React Flow, Recharts and Zod.
- Jobs use a durable database table with an inline executor or a dedicated worker process instead of
  Redis/RQ; this is a documented deviation.

### Fixed

- NetworkX degree views used as mappings.
- Impact response/schema mismatch.
- Datetime serialisation in the GitHub activity cache.
- Unknown agent output fields accepted.
- Missing risk disclaimer in reports without a risk run.
- Parallel agents on in-memory SQLite in tests.

### Verified locally

- Backend Ruff and 115 tests; frontend typecheck, lint, 9 tests and production build; MCP Ruff and 11
  tests; Alembic upgrade/downgrade on SQLite.

### Not verified

- Live GitHub import, live LLM, Playwright E2E (browser extraction stalled), Kiro MCP calls, public
  deployment, dependency and container scans.

### Post-release verification

- Docker Compose images built successfully.
- PostgreSQL migrations, backend readiness, and frontend HTTP reachability passed in a local smoke
  test.
- Frontend React Router and Zod dependencies were upgraded; npm audit now reports two moderate
  React Router findings requiring a future major upgrade.
- Backend `pytest` lock pin was upgraded to 9.0.3; backend and MCP `pip-audit` checks report no
  known vulnerabilities.
- Compose worker healthcheck corrected so the non-HTTP worker is not marked unhealthy by the API
  health probe.
