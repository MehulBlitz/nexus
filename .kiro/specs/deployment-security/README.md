# Deployment and security spec

Status: Security controls IMPLEMENTED · TESTED. Docker/Compose files are IMPLEMENTED but BLOCKED from
verification (no Docker daemon). Public deployment is BLOCKED.

## Requirements

1. Production refuses placeholder secrets, wildcard CORS and SQLite.
2. Secure cookies, CSRF, CORS allowlist, security headers and request correlation.
3. Rate limits on auth and general traffic; audit events for sensitive actions.
4. SSRF-safe GitHub access; file and size limits; no code execution.
5. Prompt-injection defences: untrusted content framing, bounded context, schema validation,
   evidence verification, no tool execution.
6. Secrets never committed, logged or returned; logs redact tokens.
7. MCP uses bearer tokens and the same ownership checks.
8. Docker Compose for frontend, backend, worker, PostgreSQL and optional MCP/Ollama.
9. Migrations run before the API starts; health checks; documented backup/recovery.
10. CI runs lint, typecheck, tests and builds; security workflow scans dependencies and secrets.

## Acceptance criteria

- [x] Production settings validation rejects unsafe configuration.
- [x] Session cookies HttpOnly/SameSite; CSRF enforced on cookie mutations.
- [x] Authorization tests cover cross-user access.
- [x] GitHub URL validation blocks non-GitHub hosts.
- [x] Log redaction tests pass.
- [x] MCP token auth and ownership reuse backend checks.
- [x] Backend/frontend/MCP test suites and builds pass locally.
- [ ] `docker compose up --build` (BLOCKED: Docker unavailable).
- [ ] PostgreSQL migrations exercised (only SQLite exercised locally).
- [ ] Container/image scanning and live deployment.
- [ ] Playwright E2E and security ZAP/browser checks.

## Design

Backend: settings validators, `security_middleware`, `rate_limit`, `security` (Argon2id, token
hashing), audit table, structured logging redaction. Deployment: multi-stage frontend image served by
nginx with `/api` proxy; backend image runs Alembic then uvicorn; worker uses the same image with
`python -m app.workers.runner`; Compose healthchecks and a named Postgres volume.

## Data / configuration

`.env.example` documents every variable. Production requires a 32+ character random
`APP_SECRET_KEY`, explicit CORS origins and a PostgreSQL URL. `JOB_EXECUTION_MODE=worker` routes jobs
to the worker process.

## API / operational contracts

`/health` (process), `/ready` (database), `/version`. Structured JSON logs with request IDs. API
errors use `{error:{code,message,request_id,details}}`.

## Tasks

- [x] Security middleware, headers, CSRF, rate limits.
- [x] Audit events.
- [x] Settings production guards.
- [x] Dockerfiles and Compose definitions.
- [x] CI and security workflow definitions.
- [x] Documentation of threat model and deployment.
- [ ] Build and run containers.
- [ ] PostgreSQL verification.
- [ ] Public deployment with HTTPS and backups.
- [ ] Load/security scanning.

## Test requirements

Backend security tests (auth, isolation, CSRF, URL validation, redaction), frontend build/tests, MCP
auth tests, CI lint/test on push. Container and deployment checks remain unverified and are reported
as such.
