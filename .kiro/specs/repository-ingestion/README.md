# Repository ingestion spec

Status: IMPLEMENTED · TESTED against a mocked GitHub API. A live public import was not verified in
this environment (network/rate limits); no claim of live success is made.

## Requirements

1. Accept only `https://github.com/owner/repository` URLs (also `http`, `www`, optional `.git`).
2. Fetch repository metadata, default branch, latest commit SHA and the recursive tree.
3. Filter to supported source files; skip binary, vendored, generated and oversized files.
4. Never execute imported code; treat all content as untrusted.
5. Create repository + snapshot records and queue indexing; expose progress and failures.
6. Respect size limits, timeouts, bounded retries and GitHub rate limits.
7. Never fetch arbitrary URLs (SSRF protection).
8. Source files are not stored permanently; content search re-fetches at the snapshot commit.

## Acceptance criteria

- [x] Invalid hosts, paths and schemes are rejected (`github.com.evil.test` is not accepted).
- [x] Tree entries over the file cap or byte cap are skipped with a recorded reason.
- [x] One malformed file produces a parser warning and does not fail the job.
- [x] Snapshot records commit SHA, branch, counts, coverage and warnings.
- [x] Re-index creates a new snapshot without corrupting history.
- [x] GitHub 403/429 maps to an explicit activity/availability message, not fake data.
- [x] Integration test imports `acme/demo` through the real service layer with only HTTP mocked.

## Design

`app/integrations/github.py` (URL parsing, metadata, tree, raw files, activity, retries),
`app/ingestion/file_filter.py` (language detection, ignore rules, size caps),
`app/services/github_service.py` (import orchestration, snapshot creation),
`app/services/indexing_service.py` (fetch, parse, graph, persistence),
`app/services/job_service.py` (durable queue + inline thread or worker process).

## Data model

`repositories`, `repository_snapshots`, `github_activity_cache`, `jobs`.

## API

`POST /repositories`, `GET /repositories`, `GET /repositories/{id}`,
`DELETE /repositories/{id}`, `POST /repositories/{id}/index`,
`GET /repositories/{id}/status`, `GET /repositories/{id}/activity`.

## Tasks

- [x] Strict URL parsing and SSRF guards.
- [x] GitHub adapter with pagination and retries.
- [x] File filtering and limits.
- [x] Snapshot creation.
- [x] Background job with progress and retry state.
- [x] Import UI with validation and live status.
- [x] Integration tests.
- [ ] Private repositories (out of scope; requires a GitHub App/OAuth and security review).
- [ ] Live import of a real public repository (not performed here).

## Tests

Unit: URL validation table, tree filtering, size limits, adapter errors. Integration: import, index,
status polling, activity cache, authorization.
