# Architecture

NEXUS is a modular monorepo: a React client, a FastAPI backend, a durable job worker, a static
analysis and graph engine, a multi-agent orchestrator, and a separate MCP server. The browser and the
MCP server are both clients of the same versioned HTTP API.

```text
┌────────────────────┐        ┌────────────────────┐
│  React + TypeScript│        │  MCP client (Kiro) │
│  React Flow        │        │  nexus_mcp         │
└─────────┬──────────┘        └─────────┬──────────┘
          │ REST / SSE (cookies+CSRF)   │ REST (bearer token)
          └──────────────┬──────────────┘
                         v
              ┌─────────────────────┐
              │   FastAPI /api/v1   │
              │ auth · ownership    │
              │ validation · limits │
              └──────┬───────┬──────┘
                     │       │
          ┌──────────v─┐   ┌─v──────────────┐
          │ PostgreSQL │   │  jobs table    │
          │  / SQLite  │   │ (durable queue)│
          └────────────┘   └─┬──────────────┘
                             │
                    ┌────────v─────────┐
                    │  Worker process  │
                    │  python -m app.  │
                    │  workers.runner  │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        v                    v                    v
  GitHub adapter      Parsers (AST/lexer)    Graph engine
  tree + raw files    files, symbols, calls  NetworkX, BFS
        │                    │                    │
        └────────────────────┴─────────┬──────────┘
                                       v
                              Snapshot + edges
                                       │
                                       v
                            Agent orchestrator
                   mapper · investigator · risk analyst
                   architecture reviewer · review planner
                                       │
                            evidence verification
                                       │
                          Investigation result / report
```

## Components

| Component | Location | Responsibility |
|---|---|---|
| API | `backend/app/api/v1` | Auth, repositories, graph, risk, investigations, agents, reports, system |
| Core | `backend/app/core` | Settings, database, security, rate limits, logging, errors, middleware |
| Models | `backend/app/models` | 16 SQLAlchemy tables with indexes and cascades |
| Repositories | `backend/app/repositories` | Query layer; no business rules in routers |
| Services | `backend/app/services` | Ingestion, indexing, search, jobs, risk, reports |
| Integrations | `backend/app/integrations/github.py` | Strict GitHub REST adapter |
| Analysis | `backend/app/analyzers` | Python AST, shared lexer for JS/TS/Java |
| Graph | `backend/app/graph` | Builder, bounded traversal, cycles, centrality, impact |
| Agents | `backend/app/agents` | Five roles, strict schemas, optional LLM |
| Orchestrator | `backend/app/orchestrator` | Parallel runs, timeouts, validation, evidence checks, synthesis |
| Frontend | `frontend/src` | Command center UI with real API data |
| MCP | `mcp-server/nexus_mcp` | Seven tools over authenticated HTTP |

## Data flow: import → index

1. `POST /repositories` validates the URL, fetches metadata and the default branch, creates the
   repository and snapshot, and queues an `index_repository` job.
2. The worker/inline executor fetches the recursive tree at the commit, filters files, fetches raw
   content with concurrency and byte limits, parses each file, persists `CodeNode`s, builds edges,
   then updates snapshot counts and coverage.
3. The UI polls `/status` and shows real progress. Malformed files become warnings.

## Data flow: investigation

1. `POST /repositories/{id}/investigations` requires an indexed snapshot and queues a job.
2. The orchestrator builds a bounded context (files, symbols, edges, metrics, risk summary) and runs
   five agents in parallel with per-agent sessions and timeouts.
3. Each output is validated against a strict Pydantic model. Evidence file paths and line ranges are
   checked against indexed nodes; unsupported references are dropped or clamped.
4. The synthesised result, per-agent status and limitations are stored on the investigation.
5. The UI polls (or consumes SSE) and renders hypotheses, evidence, plan and agent timings.

## Key decisions

| Decision | Reason | Consequence |
|---|---|---|
| DB-backed job queue instead of Redis/RQ | No Redis in the authoring environment; durability and visibility matter more than throughput | Single worker table; polling can be replaced by Redis later without API changes. `REDIS_URL` is unused. |
| Python `ast`; documented lexer for JS/TS/Java | `tree-sitter` has no Python 3.15 wheel and its source build fails here | Lexer coverage is explicitly reported; it is not full semantic parsing. |
| Opaque session cookies, not JWT | Simpler revocation; no token in browser storage | Requires CSRF protection on cookie mutations. |
| No source stored permanently | Limits exposure and storage | Content search re-fetches from GitHub at the snapshot commit. |
| Snapshot-scoped analysis | Reproducibility | Re-index creates a new snapshot; analyses are tied to one commit. |
| Risk signals renormalise | Never invent missing data | Confidence reflects the share of weight that was available. |
| MCP calls the HTTP API | One authorization/business-logic boundary | MCP requires a personal API token; no database coupling. |

## Bounds

- `MAX_INDEX_FILES` (default 400), `MAX_FILE_BYTES` (256 KiB), `MAX_TOTAL_BYTES` (20 MiB).
- Graph view capped at 800 requested / 250 used by the UI; traversal 1–8 levels; impact 4 by default.
- Agent contexts cap files, symbols and characters; per-agent timeout; only one retry.
- Report and finding payloads are bounded per snapshot.

## Known deviations

- Redis is not used; jobs are durable rows executed by an inline thread (development) or a worker
  process (`JOB_EXECUTION_MODE=worker`).
- Email verification is not implemented because no transactional email provider is configured.
- Private repositories, write actions and code execution are out of scope.
- Docker and PostgreSQL passed a local Compose smoke test; public deployment remains unverified.
