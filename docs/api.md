# API

Base path: `/api/v1`. OpenAPI is served at `/api/v1/openapi.json` (Swagger UI at `/docs` in
non-production environments).

## Conventions

- Authentication: `nexus_session` HttpOnly cookie, or `Authorization: Bearer <personal API token>`.
- Cookie-authenticated mutations require `X-CSRF-Token` matching the readable `nexus_csrf` cookie.
- Requests with an `Origin` header must match the configured allowlist for cookie mutations.
- Errors: `{"error": {"code": "...", "message": "...", "request_id": "...", "details": ...}}`.
- Pagination: `limit` and `offset`, responses `{items,total,limit,offset}`.
- IDs are UUID strings; timestamps are ISO-8601 UTC.
- Every response carries `X-Request-ID`; send your own to correlate logs.
- Resource ownership is enforced on every repository-scoped call; another user's resource returns 404.

## Authentication

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Creates user + session; 409 on duplicate email |
| POST | `/auth/login` | Sets session and CSRF cookies |
| POST | `/auth/refresh` | Rotates the session (cookie session required) |
| POST | `/auth/logout` | Revokes session, clears cookies |
| GET | `/auth/me` | Current user |
| POST | `/auth/change-password` | Revokes other sessions |
| POST | `/auth/account` | Deletes the account and owned data |
| GET/POST | `/auth/tokens` | List/create personal API tokens |
| DELETE | `/auth/tokens/{id}` | Revoke a token |

## Repositories and code intelligence

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/repositories` | List / import a public GitHub repository |
| GET/DELETE | `/repositories/{id}` | Detail / delete (cascades snapshots, analyses) |
| POST | `/repositories/{id}/index` | Queue a new snapshot |
| GET | `/repositories/{id}/status` | Repository status, active job, latest snapshot |
| GET | `/repositories/{id}/activity` | GitHub commits/PRs/issues/workflows with availability |
| GET | `/repositories/{id}/overview` | Languages, counts, modules, coverage, warnings |
| GET | `/repositories/{id}/files` | Indexed files (paginated) |
| GET | `/repositories/{id}/symbols` | Symbol search (`q`, `language`) |
| GET | `/repositories/{id}/search` | Path/symbol/content search (`q`, `language`, `directory`) |

## Graph

| Method | Path | Notes |
|---|---|---|
| GET | `/repositories/{id}/graph` | Nodes/edges; `node_types`, `relationship_types`, `search`, `limit` |
| GET | `/repositories/{id}/graph/metrics` | Cycles, components, centrality, missing evidence |
| GET | `/repositories/{id}/graph/nodes/{node_id}` | Node + neighbourhood |
| GET | `/repositories/{id}/graph/dependencies/{node_id}` | `direction=dependencies|dependents`, `max_depth=1..8` |
| POST | `/repositories/{id}/graph/impact` | `{node_id|file_path, direction, max_depth}` |

## Risk

| Method | Path | Notes |
|---|---|---|
| GET | `/repositories/{id}/risks` | Latest findings; `severity` filter |
| GET | `/repositories/{id}/risks/summary` | Score, confidence, signal availability, weights |
| GET | `/repositories/{id}/risks/{finding_id}` | Finding + per-signal evidence |
| POST | `/repositories/{id}/risks/analyze` | Queue analysis; 202 with `job_id` |

Risk scores are prioritisation heuristics. They are never a probability of failure.

## Investigations and agents

| Method | Path | Notes |
|---|---|---|
| POST/GET | `/repositories/{id}/investigations` | Create / list |
| GET | `/investigations/{id}` | Detail with agent runs and result |
| POST | `/investigations/{id}/cancel` | Cancel unfinished investigation |
| GET | `/investigations/{id}/events` | SSE progress |
| GET | `/investigations/{id}/evidence` | Evidence references and line-count limits |
| GET | `/agents` | Agent catalogue |
| GET | `/agents/runs` | Recent runs (`repository_id` optional) |
| GET | `/agents/runs/{id}` | One run |
| GET | `/agents/stats` | Counts and average execution time |

## Reports and system

| Method | Path | Notes |
|---|---|---|
| POST/GET | `/repositories/{id}/reports` | Generate / list reports |
| GET | `/reports/{id}` | Report detail with Markdown |
| GET | `/reports/{id}/export` | `text/markdown` attachment |
| GET | `/health` | Process liveness |
| GET | `/ready` | Database readiness |
| GET | `/version` | Name, version, environment |
| GET | `/jobs/{id}` | Job status/progress (authenticated) |

## Status codes

`200` OK · `201` created · `202` queued · `204` no content · `400` malformed · `401` unauthenticated ·
`403` CSRF/origin/forbidden · `404` not found or not owned · `409` conflict (duplicate, not indexed,
already finished) · `413` request too large · `422` validation · `429` rate limited · `503` dependency
unavailable.
