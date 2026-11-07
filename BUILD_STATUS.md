# BUILD_STATUS

Last updated: Phase 0 + Phase 1 session.

**Status values:** NOT WORKED ON · IN PROGRESS · BLOCKED · IMPLEMENTED · TESTED · VERIFIED
- **NOT WORKED ON** = not started, or cannot be done/verified in the authoring sandbox.
- **TESTED** = automated tests ran and passed (evidence below).
- **VERIFIED** is reserved for end-to-end evidence in a real environment. Nothing is VERIFIED yet.

## Summary table

| Area | Status | Evidence |
|---|---|---|
| Monorepo + `.kiro/` structure | TESTED | `.kiro/` present and not git-ignored (`git check-ignore .kiro` returns nothing) |
| Kiro steering (5 docs) | IMPLEMENTED | `.kiro/steering/*.md` |
| Kiro custom agents (4) | IMPLEMENTED | `.kiro/agents/*.md` (definitions only, never run inside Kiro) |
| Kiro foundation spec | IMPLEMENTED | `.kiro/specs/foundation/` requirements, design, tasks |
| Other 11 Kiro specs | NOT WORKED ON | stub README per folder |
| Kiro hooks | NOT WORKED ON | must be created through the Kiro UI |
| Kiro MCP connection / usage log evidence | NOT WORKED ON | needs a real Kiro session |
| Backend foundation (Phase 1) | TESTED | 26 pytest tests pass; Ruff clean; live `uvicorn` served `/health`, `/ready`, `/version` and the standard 404 body |
| Alembic wiring | TESTED | `alembic upgrade head` exit 0 on SQLite; no models or migrations yet |
| Database (PostgreSQL) | NOT WORKED ON | only SQLite exercised; no Postgres in sandbox |
| Frontend shell (Phase 0/3 skeleton) | TESTED | `tsc` strict, ESLint, 9 Vitest tests, production build, `npm audit` 0 vulnerabilities; rendered in Chromium against live backend (pass, fail and 390px mobile states) |
| Authentication | NOT WORKED ON | Phase 2 |
| Full frontend (pages, graph UI) | NOT WORKED ON | Phase 3+ |
| GitHub import / activity | NOT WORKED ON | Phases 4, 10 |
| Code intelligence | NOT WORKED ON | Phase 5 |
| Knowledge graph | NOT WORKED ON | Phase 6 |
| Risk engine | NOT WORKED ON | Phase 7 |
| Multi-agent system / Ollama | NOT WORKED ON | Phase 8 (no model available here) |
| Investigations | NOT WORKED ON | Phase 9 |
| MCP server | NOT WORKED ON | Phase 11 |
| Reports | NOT WORKED ON | Phase 12 |
| Background worker (RQ/Redis) | NOT WORKED ON | no worker code; Redis not exercised |
| Dockerfiles + `compose.yaml` | IMPLEMENTED | written, YAML parses; **never built or run** (no Docker in sandbox) |
| Docker Compose end-to-end | NOT WORKED ON | cannot run here |
| Playwright E2E scenario | NOT WORKED ON | only an ad-hoc screenshot script was used, not committed as a test |
| CI workflows (`.github/workflows`) | NOT WORKED ON | folder exists, no workflows yet |
| Security docs / hardening (Phase 13) | NOT WORKED ON | foundation guards only: prod secret/CORS/SQLite checks, log redaction, no stack traces to clients |
| Production deployment, public URL | NOT WORKED ON | cannot be done in this environment |
| Demo repo, video, Devpost submission | NOT WORKED ON | outside what can be done here |
| Screenshots in `docs/screenshots/` | NOT WORKED ON | ad-hoc shots taken in `/tmp`, not committed |

## Completed in this session
- Phase 0: skeleton, ignore files, `.env.example`, MIT license, Makefile, steering, agents, foundation spec.
- Phase 1: settings with production validation; JSON logging with secret redaction; correlation IDs; consistent error bodies; SQLAlchemy engine + readiness check; Alembic; `/api/v1/{health,ready,version}`.

## Bugs found and fixed by tests
1. Starlette's built-in 404s bypassed the standard error body (wrong `HTTPException` class registered).
2. Log redaction left bearer tokens visible when preceded by `Authorization:`; fixed by ordering the patterns.
3. A proxy 5xx with no API body showed "Internal Server Error" in the UI; it now says the API is unreachable.
4. Vitest 3 had critical audit findings (tinypool); upgraded to 5.1.0 and pinned a patched `minimatch` via `overrides`.

## Known limitations
- `backend/requirements.lock` is a filtered `pip freeze` of the sandbox install, not a hash-locked resolver lock.
- `compose.yaml` lists only services that exist (`db`, `redis`, `backend`, `frontend`). `worker` and `mcp-server` come later. The `backend` image has not been built.
- The frontend loads IBM Plex from Google Fonts; screenshots here used fallback fonts because the sandbox blocks that host.
- Backend Python deps were audited by version pin only; `pip-audit` was not run.

## Next
Phase 2 (authentication) needs its own spec first. Awaiting approval to start.
