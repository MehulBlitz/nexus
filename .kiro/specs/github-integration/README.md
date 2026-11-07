# GitHub integration spec

Status: IMPLEMENTED · TESTED with mocked HTTP. Live GitHub activity was not verified here.

## Requirements

1. Read public repository metadata, branches, commits, pull requests, issues and workflow runs.
2. Paginate and respect rate limits; map 403/429 to an unavailable reason.
3. Cache activity briefly in the database; never present cache as live without a timestamp.
4. Link evidence back to GitHub pages.
5. Never create a fake CI status; unavailable data must say why.
6. No write actions and no private repository access in this release.
7. Optional token support improves rate limits but is never mandatory.

## Acceptance criteria

- [x] Metadata, default branch and commit SHA fetched via documented REST endpoints.
- [x] Commits, PRs and issues parsed into stable items.
- [x] Workflow runs returning 403 produce an unavailable section with the GitHub message.
- [x] Activity is cached with `fetched_at` and a reason per section.
- [x] Summary distinguishes retrieved and unavailable sections.
- [x] UI shows each section with availability badges and source links.
- [x] Cache serialisation uses ISO strings (regression fixed).
- [ ] Live API verification with a real public repository (not performed).

## Design

`app/integrations/github.py` methods: `get_repository`, `get_branch`, `get_tree`, `fetch_raw_file`,
`list_commits`, `get_commit`, `list_pull_requests`, `list_issues`, `list_workflow_runs`.
`app/services/github_service.py` orchestrates, caches and builds `RepositoryActivity`.
Cache table: `github_activity_cache`.

## Data model

`github_activity_cache` (repository, kind, payload JSON, fetched_at, reason).

## API

`GET /repositories/{id}/activity`. Read-only.

## Tasks

- [x] REST adapter and pagination.
- [x] Error/rate-limit mapping.
- [x] Cache.
- [x] Activity dashboard section.
- [x] Evidence links.
- [x] Tests.
- [ ] OAuth/GitHub App for private repositories (out of scope).
- [ ] Workflow logs and check annotations.

## Tests

Adapter unit tests for URL parsing and error mapping; integration fixture returns commits/PRs/issues
and a deliberate 403 for workflows, asserting the unavailable reason.
