# NEXUS architecture steering

- **Monorepo:** `frontend/`, `backend/`, `mcp-server/`, `shared/`, `infrastructure/`, `docs/`, `.kiro/`.
- **Frontend:** React + TypeScript (strict), Vite, Tailwind. Talks only to the REST API (`/api/v1`) and SSE. Never touches the database.
- **Backend:** FastAPI. Layering: `api` -> `services` -> `repositories` -> `models`. Routes hold no business logic.
- **Database:** PostgreSQL in production, SQLite allowed for dev/tests. Every schema change ships as an Alembic migration. Timestamps are UTC.
- **Worker:** durable `jobs` rows executed by a separate process (`python -m app.workers.runner`) or an inline development thread. Redis/RQ is not used in this implementation; jobs expose status and progress.
- **Graph engine:** NetworkX over parsed nodes/edges. Bounded traversal only.
- **Agents:** explicit responsibility contracts, Pydantic-validated outputs (`extra="forbid"`), evidence verification, timeouts, bounded retries. Deterministic fallback when no LLM is configured.
- **MCP server:** separate process, calls the authenticated backend over HTTP, reuses backend services, read-only by default.
- **Security boundaries:** auth at the API edge, ownership checks in services, repository content treated as untrusted input everywhere.
