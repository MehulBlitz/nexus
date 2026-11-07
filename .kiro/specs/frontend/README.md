# Frontend spec

Status: IMPLEMENTED · TESTED (TypeScript strict, ESLint, Vitest, production build). Browser E2E was
not run in this environment; screenshots of the running UI are captured separately.

## Requirements

1. Dark, information-dense developer command center; no fabricated statistics.
2. Pages: landing, login/register, dashboard, repositories, repository overview, graph, risk center,
   investigations (list/detail), agents, reports, settings.
3. Real API data only, with loading, empty, error and success states.
4. Graph explorer supports search, filter, selection, traversal, impact, minimap and reset.
5. Forms validate with Zod; destructive actions require confirmation.
6. Accessible labels, keyboard focus, responsive layout.
7. Session restore via `/auth/me`; unauthenticated app routes redirect to login.
8. Mutations send the CSRF header; credentials are included.
9. Do not store tokens in browser storage.

## Acceptance criteria

- [x] All routes exist and deep-link.
- [x] No hardcoded repository statistics; every number comes from an API response.
- [x] Import form rejects non-GitHub URLs before submission.
- [x] Indexing progress polls until the job finishes.
- [x] Risk UI shows signals, evidence and the "not a probability" statement.
- [x] Investigation UI polls while running and displays real agent runs.
- [x] Reports render Markdown and download the exported file.
- [x] Settings expose tokens, password change and account deletion.
- [x] Typecheck, lint, unit tests and production build pass.
- [ ] Playwright scenario executed (browsers not installed; not claimed).

## Design

React 18 + Vite + Tailwind 4. TanStack Query for server state; Zustand for the session mirror;
React Router for routes; `@xyflow/react` for the graph; Recharts for language/risk charts; Zod for
forms. `lib/api.ts` centralises fetch, error mapping and CSRF. Page-level states avoid blank screens.

## Data / contracts

Types in `src/types/api.ts` mirror Pydantic response schemas. The API base is `/api/v1` and Vite
proxies it in development.

## Tasks

- [x] Layout, navigation, design tokens.
- [x] Landing and auth.
- [x] Dashboard.
- [x] Repository import/management/overview.
- [x] Graph explorer.
- [x] Risk center.
- [x] Investigation workflow.
- [x] Agents and reports.
- [x] Settings.
- [x] Unit tests and build.
- [ ] E2E and visual regression suite.

## Tests

Vitest: API probe error mapping and system status states. TypeScript strict compilation. ESLint.
Production Vite build. Manual browser review is recorded in the build status, not claimed as E2E.
