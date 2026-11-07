# BUILD_STATUS

Last updated: GitHub Actions E2E verification run 42371333297.

**Allowed status values:** NOT STARTED · IN PROGRESS · BLOCKED · IMPLEMENTED · TESTED · VERIFIED

- **IMPLEMENTED** — code/config exists and was reviewed, but its behaviour is not covered by an
  executed check here.
- **TESTED** — an automated check was executed in this environment and passed (evidence below).
- **VERIFIED** — end-to-end evidence in a real environment. Nothing in this file is VERIFIED except
  where explicitly stated; public deployment and Kiro MCP execution remain pending.

## Summary

| Area | Status | Evidence |
|---|---|---|
| Monorepo structure | IMPLEMENTED | `backend/`, `frontend/`, `mcp-server/`, `shared/`, `infrastructure/`, `docs/` |
| `.kiro/` steering (5) | IMPLEMENTED | `.kiro/steering/*.md`; not git-ignored |
| `.kiro/` specs (foundation + 11) | IMPLEMENTED | requirements/acceptance/design/tasks/tests in each spec |
| Kiro custom agents (4) | IMPLEMENTED | definitions only; never executed in Kiro |
| Kiro hooks | IMPLEMENTED (proposal) | `.kiro/hooks/README.md`; **not installed** |
| Kiro MCP connection / usage evidence | BLOCKED | requires a real Kiro session |
| Backend API (auth, repositories, graph, risk, investigations, agents, reports, system) | TESTED | `pytest` 115 passed; `ruff check .` clean |
| Authentication + authorization | TESTED | auth unit/integration tests, cross-user 404 checks |
| Database models + migration | TESTED | 16 tables; Alembic upgrade → downgrade → upgrade on SQLite |
| PostgreSQL | TESTED | Docker Compose PostgreSQL 16; migrations and `/api/v1/ready` passed |
| GitHub import + indexing | TESTED | integration flow with mocked HTTP transport |
| Live public GitHub import | TESTED | Real `octocat/Hello-World` imports completed through the worker at 100% |
| Code intelligence (Python AST, JS/TS/Java lexer) | TESTED | analyzer unit tests + integration counts/warnings |
| Knowledge graph + traversal + impact | TESTED | unit, Hypothesis properties, integration |
| Risk engine | TESTED | unit, property and integration; evidence persisted |
| Multi-agent orchestration | TESTED | fake-repository flow; all five agents complete; failures isolated |
| Live LLM (Ollama/OpenAI-compatible) | BLOCKED | no model/server available; deterministic fallback tested |
| Investigation workflow (backend) | TESTED | queue → agents → evidence verification → result |
| Frontend pages + graph explorer + forms | TESTED | `tsc --noEmit`, ESLint, 9 Vitest tests, production build |
| Frontend browser rendering | TESTED | local dev server; screenshots captured (landing, dashboard, repositories) |
| Playwright E2E scenario | VERIFIED | GitHub Actions run [42371333297](https://github.com/MehulBlitz/nexus/actions/runs/42371333297), job [128399905969](https://github.com/MehulBlitz/nexus/actions/runs/42371333297/job/128399905969): Chromium install, Compose startup, critical flow, report upload, and cleanup passed |
| MCP server (7 tools) | TESTED | 11 tests with `httpx.MockTransport`; Ruff clean |
| Live MCP calls from Kiro | BLOCKED | requires Kiro client; not performed |
| Reports + Markdown export | TESTED | integration report generation and export content |
| Background jobs | TESTED | durable jobs table; inline executor and worker entry point |
| Dockerfiles + Compose | TESTED | images built; PostgreSQL/backend/worker startup smoke passed; frontend HTTP 200; worker healthcheck corrected |
| Redis/RQ | NOT STARTED (deviation) | replaced by durable database queue; documented |
| CI workflows | IMPLEMENTED | `.github/workflows/ci.yml`, `security.yml`, manual `.github/workflows/e2e.yml`; E2E workflow externally verified |
| Security hardening | TESTED (application controls) | auth/CSRF/ownership/URL/redaction tests; no external scan |
| Production deployment / HTTPS | BLOCKED | not performed |
| Public URL / video / Devpost | NOT STARTED | outside this environment |
| Playwright browsers | TESTED | Chromium installation passed on GitHub Actions Ubuntu 24.04; local Windows extraction remains unavailable |
| Dependency audits (`pip-audit`, `npm audit`) | TESTED | backend/MCP/npm audits clean; Trivy/Gitleaks unavailable |

## Executed checks (actual results)

| Command | Result |
|---|---|
| `cd backend && python -m ruff check .` | All checks passed |
| `cd backend && python -m pytest -q` | **115 passed** |
| `cd frontend && npx tsc --noEmit` | exit 0 |
| `cd frontend && npm run lint` | exit 0 |
| `cd frontend && npx vitest run` | **9 passed** (2 files) |
| `cd frontend && npm run build` | exit 0; production bundle emitted (Vite warned about a >500 kB chunk) |
| `cd mcp-server && PYTHONPATH=. pytest -q` | **11 passed** |
| `cd mcp-server && python -m ruff check .` | All checks passed |
| Alembic on SQLite | upgrade → downgrade base → upgrade, exit 0 (recorded in migration run) |
| Docker Compose | images built; PostgreSQL/backend healthy; `/api/v1/ready` passed; frontend returned HTTP 200 |
| `cd frontend && npm audit --audit-level=high --omit=dev` | 0 vulnerabilities after React Router 7.18.5 upgrade |
| `pip-audit` | backend and MCP lockfiles clean; backend audit excluded Windows-incompatible `uvloop` |
| GitHub Actions E2E run 42371333297 | **passed** | Ubuntu 24.04; Chromium install, Compose startup, critical flow, report upload, and cleanup all passed |

## Bugs found and fixed during integration

1. NetworkX degree views (`InDegreeView`) were treated as dicts in risk scoring and the mapper.
2. Impact analysis returned a shape that did not match `ImpactResult` (missing `node`), causing a 500.
3. Activity cache stored `datetime` objects in a JSON column, causing a `StatementError`.
4. Agent output schemas did not reject unknown fields; strict models added.
5. Report Markdown omitted the heuristic disclaimer when no risk run existed.
6. In-memory SQLite could not serve parallel agent threads; tests now use a file database.
7. Test assumption about TypeScript file count corrected (two TS files, not one).

## Known limitations / deviations

- Redis/RQ is not implemented; the durable `jobs` table plus inline/worker executor is used.
- `tree-sitter` is unavailable for the installed Python 3.15; JS/TS/Java use a lexer.
- Risk weights are assumptions, not calibrated probabilities.
- Rate limiting is in-process; SSE state is in-process.
- Kiro MCP calls remain unverified; live GitHub indexing completed for a small public repository.
- `backend/requirements.lock` is a filtered freeze/constraint file, not a hash-locked resolver output.
- `mcp-server/requirements.lock` is a compatible pin list generated manually.
- CI and security workflows still need separate successful runs; the manual E2E workflow is verified.

## Next steps to reach full verification

1. Import a real public demo repository and capture graph/risk/investigation screenshots.
2. Run Trivy/Gitleaks when available.
3. Connect Kiro to the MCP server, call at least two tools, and capture evidence.
4. Deploy behind HTTPS with backups, then mark deployment VERIFIED only with a live URL.
