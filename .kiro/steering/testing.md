# Testing steering

- **Unit:** pytest for backend, Vitest + React Testing Library for frontend.
- **Integration:** test database, mocked external HTTP.
- **E2E:** Playwright for the full import-to-report scenario.
- **Property-based:** Hypothesis for graph, risk, ingestion and agent invariants.
- **Static:** Ruff, ESLint, `tsc --noEmit`.
- **CI:** all of the above must run and pass. Failed checks are never hidden.
- **Reporting:** never claim a test passed without execution output.
