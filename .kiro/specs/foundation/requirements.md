# Foundation: requirements

## R1 Project structure
**User story:** As a developer, I want a documented monorepo so I can find and extend any part of NEXUS.
- R1.1 The repository contains `frontend/`, `backend/`, `mcp-server/`, `shared/`, `infrastructure/`, `docs/`, `.kiro/`.
- R1.2 `.kiro/` is committed and never listed in `.gitignore`.
- R1.3 `.env.example` documents every configuration variable with placeholders only.

## R2 Backend service
**User story:** As an operator, I want a health-checked API so I can tell whether NEXUS is running.
- R2.1 `GET /health` returns 200 when the process is alive, without touching the database.
- R2.2 `GET /ready` returns 200 only when the database is reachable, otherwise 503 with the failing check named.
- R2.3 `GET /version` returns the application name and version.
- R2.4 All endpoints live under `/api/v1`.

## R3 Configuration
- R3.1 All settings come from environment variables, validated at startup.
- R3.2 In production, a missing or placeholder `APP_SECRET_KEY` aborts startup.
- R3.3 Production rejects a wildcard CORS origin.

## R4 Observability
- R4.1 Every request has a correlation ID (accepted from `X-Request-ID` if valid, else generated) returned in the response header.
- R4.2 Logs are structured JSON and include the correlation ID.
- R4.3 Logs never include secrets.

## R5 Error handling
- R5.1 Errors return a consistent body `{error: {code, message, request_id}}`.
- R5.2 Unhandled exceptions return a generic 500 body and never a stack trace.

## R6 Persistence wiring
- R6.1 SQLAlchemy and Alembic are configured; migrations run with `alembic upgrade head`.
- R6.2 Timestamps are stored in UTC.

## R7 Frontend shell
- R7.1 The shell builds with TypeScript strict mode.
- R7.2 It displays real `/health`, `/ready` and `/version` results, including failure states, with no fabricated data.

## Test requirements
Each requirement above has at least one automated test or a documented build check.
