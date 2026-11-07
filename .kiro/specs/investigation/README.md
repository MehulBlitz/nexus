# Investigation spec

Status: IMPLEMENTED · TESTED (backend integration). The UI is built and typechecked; no Playwright
E2E run was performed.

## Requirements

1. Create an investigation from a question and optional scope, bound to the latest snapshot.
2. Run asynchronously with progress, status, cancellation and failure details.
3. Show agents involved, execution history, findings, evidence, recommendations and limitations.
4. Every source claim points to a real indexed file and line range; unsupported claims are dropped.
5. Provide SSE progress events and polling fallback.
6. Persist history per repository and enforce ownership.
7. Distinguish deterministic analysis from AI-generated reasoning.

## Acceptance criteria

- [x] Investigation cannot start before indexing (409).
- [x] Job persisted; status transitions queued → running → completed/failed.
- [x] Agent runs persisted with timings and errors.
- [x] Evidence verification records checked files and issues.
- [x] Result includes summary, hypotheses, plan/actions, limitations and AI note.
- [x] Cancel marks unfinished agent runs skipped.
- [x] SSE endpoint streams progress and a terminal event.
- [x] Cross-user access returns 404.
- [x] UI polls while running and renders the timeline, hypotheses and plan.
- [ ] Playwright E2E scenario including investigation (not run).

## Design

`app/models/investigation.py`, `app/repositories/investigations.py`,
`app/services/job_service.py` (job type `run_investigation`),
`app/orchestrator/orchestrator.py`, `app/api/v1/investigations.py` (create/list/detail/cancel/events/
evidence). UI: `features/investigations/InvestigationsPage.tsx`.

## Data model

`investigations` (question, scope, status, progress, result JSON, ai_used, timestamps) and
`agent_runs`.

## API

`POST /repositories/{id}/investigations`, `GET /repositories/{id}/investigations`,
`GET /investigations/{id}`, `POST /investigations/{id}/cancel`,
`GET /investigations/{id}/events` (SSE), `GET /investigations/{id}/evidence`.

## Tasks

- [x] Model and migration.
- [x] Context retrieval.
- [x] Orchestrator integration.
- [x] Evidence verification.
- [x] SSE and polling.
- [x] UI with timeline/evidence/plan.
- [x] Backend integration tests.
- [ ] Committed E2E test run.

## Tests

Integration: submit question, execute job, all agents complete, evidence files exist in the snapshot,
AI marked unavailable without a provider. Security: another user cannot read or cancel.
