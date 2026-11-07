# Deployment

## Status

The Dockerfiles and Compose file are written but **were not built or run** in the authoring
environment (no Docker daemon). PostgreSQL was not available; migrations were exercised against
SQLite only. Treat container and production steps as unverified until you run them.

## Local development without Docker

Prerequisites: Python 3.12+, Node 22+, npm.

```bash
cp .env.example .env          # edit APP_SECRET_KEY; SQLite is fine for development

cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api to :8000
```

Jobs run inline by default (`JOB_EXECUTION_MODE=inline`). To use the worker process:

```bash
# backend/.env
JOB_EXECUTION_MODE=worker
python -m app.workers.runner
```

MCP server:

```bash
cd mcp-server
pip install .
NEXUS_API_URL=http://localhost:8000 NEXUS_API_TOKEN=<token> python -m nexus_mcp.server
```

Create the token in **Settings → API tokens** after registering.

## Docker Compose

```bash
cp .env.example .env
# Replace APP_SECRET_KEY, POSTGRES_PASSWORD, POSTGRES_USER, POSTGRES_DB, CORS_ORIGINS, FRONTEND_URL.
docker compose up --build
```

Services: `db` (PostgreSQL 16), `backend` (migrations + uvicorn), `worker`, `frontend` (nginx on
`:5173`). Optional profiles:

```bash
docker compose --profile mcp run --rm mcp     # stdio MCP client
docker compose --profile ai up -d ollama      # local inference
```

`MCP_SERVICE_TOKEN` must contain a personal API token. Redis is intentionally absent: the durable
`jobs` table is the queue. Set `MCP_ALLOW_WRITES=1` only if you want MCP clients to create
investigations/reports.

## Production checklist

1. `APP_ENV=production` and a random `APP_SECRET_KEY` of 32+ characters.
2. PostgreSQL URL (`postgresql+psycopg://...`); persistent volume; automated backups.
3. Explicit `CORS_ORIGINS` and `FRONTEND_URL`; HTTPS terminated by a reverse proxy.
4. Secure cookies (default in production), HSTS at the proxy, request size limits at the proxy.
5. Run `alembic upgrade head` before starting API replicas.
6. One or more workers (`python -m app.workers.runner`) with the same database.
7. Health checks on `/api/v1/health` and `/api/v1/ready`.
8. Secrets from a secret manager, never the image.
9. Rate limiting at the edge if running more than one API replica (in-process limits are per replica).
10. Run `pip-audit`, `npm audit`, and the CI workflows before exposing the service.
11. Set `GITHUB_TOKEN` to raise GitHub API limits if many imports are expected.
12. Configure `AI_PROVIDER=none` unless you have reviewed the privacy implications of sending code
    excerpts to a model provider.

## Database migrations

```bash
cd backend
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic current
```

The initial migration creates 16 tables and indexes. Generated with autogenerate, reviewed, and
exercised on SQLite (upgrade → downgrade → upgrade). PostgreSQL execution remains unverified.

## Backup and recovery

- PostgreSQL: use `pg_dump --format=custom` on a schedule, store off-host, encrypt at rest, and test
  restores. Repository source is not stored, so a restore only needs the database.
- Docker volume `db_data` is the persistent state; deleting it destroys accounts and analyses.
- Redis is not part of the state.
- Account deletion cascades owned rows; there is no soft-delete recovery.

## Observability

- Structured JSON logs with request IDs; API responses expose `X-Request-ID`.
- `/health` is process liveness; `/ready` checks the database.
- Jobs expose status, progress, attempts and error messages; `/api/v1/jobs/{id}` is authenticated.
- No metrics/tracing exporter is implemented.

## Verified vs unverified

| Step | Status |
|---|---|
| Backend runs on SQLite, tests pass | Verified locally |
| Alembic upgrade/downgrade on SQLite | Verified locally |
| Frontend builds and runs | Verified locally |
| Docker images / Compose | Written, unverified |
| PostgreSQL | Unverified |
| Public HTTPS deployment | Not performed |
| Backup/restore drill | Not performed |
