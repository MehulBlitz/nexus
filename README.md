# NEXUS

Understand your codebase. Investigate problems. See engineering risk with the evidence behind it.

> **Status: foundation build.** Only the backend foundation and a status shell exist.
> Authentication, repository import, the graph, risk analysis, agents, reports and MCP are **not built yet**. See [BUILD_STATUS.md](BUILD_STATUS.md) for exactly what is done and tested.

## What works today
- FastAPI backend with `/api/v1/health`, `/api/v1/ready` (checks the database) and `/api/v1/version`
- Validated environment settings, structured JSON logs with secret redaction, request correlation IDs, consistent error responses
- SQLAlchemy and Alembic wiring (no models yet)
- React + TypeScript + Tailwind shell that shows the real results of those three endpoints

## Repository layout
```
.kiro/       steering, specs, custom agents (committed on purpose)
backend/     FastAPI app, migrations, tests
frontend/    Vite + React + TypeScript shell
mcp-server/  placeholder (Phase 11)
shared/ infrastructure/ docs/ tests/
```

## Run locally (no Docker)
Prerequisites: Python 3.12+, Node 22+.

```bash
# backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --port 8000        # uses SQLite by default in development

# frontend (second terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173, proxies /api to :8000
```

## Tests and checks
```bash
make backend-lint backend-test
make frontend-check frontend-build
cd frontend && npm test
```

## Docker
`compose.yaml` and the Dockerfiles are written but **have not been built or run yet**. Copy `.env.example` to `.env`, replace every placeholder, then `docker compose up --build`.

## Configuration
Everything comes from environment variables; see `.env.example`. In production the app refuses to start with a placeholder or short `APP_SECRET_KEY`, a wildcard CORS origin, or SQLite.

## Security notes
Only foundation protections exist so far (see BUILD_STATUS.md). Do not deploy this build as a public service.

## Kiro
Steering, one spec and four custom agent definitions live in `.kiro/`. Hooks and the MCP connection are not set up yet.

## License
MIT
