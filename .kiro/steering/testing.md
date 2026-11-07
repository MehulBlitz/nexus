# Testing steering

- **Unit:** pytest for backend, Vitest + React Testing Library for frontend.
- **Integration:** test database, mocked external HTTP.
- **E2E:** Playwright scenario for the full import-to-report flow (`frontend/tests/e2e/`). Browsers were not installed in the authoring environment, so it is committed but not executed.
- **Property-based:** Hypothesis for graph, risk, ingestion and agent invariants.
- **Static:** Ruff, ESLint, `tsc --noEmit`.
- **CI:** all of the above must run and pass. Failed checks are never hidden. Workflows are committed; they were not executed on GitHub from the authoring environment.
- **Reporting:** never claim a test passed without execution output.
