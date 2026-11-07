# Foundation: design

## Backend layout
`app/core/` settings, logging, errors, middleware, database. `app/api/v1/` routers. `app/main.py` application factory `create_app()`.

## Settings
`pydantic-settings` `Settings` class reads env vars. `get_settings()` is cached. A validator enforces the production rules in R3.

## Middleware
`CorrelationIdMiddleware` reads or generates the ID (accepted only if it matches `^[A-Za-z0-9._-]{8,64}$`), stores it in a `ContextVar`, and sets the response header. A logging filter injects it into every record.

## Errors
`AppError(code, message, status_code)` base class. Handlers map `AppError`, `RequestValidationError`, `HTTPException` and bare `Exception` to the standard body.

## Database
Sync SQLAlchemy 2.0 engine built from `DATABASE_URL`. `check_database()` runs `SELECT 1`. A `Base` declarative class with a `utcnow()` helper is the home for later models. Alembic `env.py` reads the same URL.

## Endpoints
| Method | Path | Behaviour |
|---|---|---|
| GET | /api/v1/health | liveness, no DB |
| GET | /api/v1/ready | DB check, 503 on failure |
| GET | /api/v1/version | name, version, environment |

## Frontend shell
Vite + React + TypeScript strict + Tailwind. A single status view calls the three endpoints through a typed API client and renders loading, success and error states.

## Out of scope
Auth, ingestion, parsing, graph, risk, agents, MCP (later specs).
