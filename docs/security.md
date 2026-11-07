# Security

## Threat model

| Asset | Threat | Control |
|---|---|---|
| Credentials | Offline cracking, token theft | Argon2id; opaque HttpOnly session cookies; API tokens stored as hashes with prefixes |
| User data | Cross-tenant access | Ownership checks on every repository-scoped query; 404 for foreign resources |
| Mutations | CSRF | Double-submit CSRF token plus origin validation for cookie sessions |
| Imported repositories | SSRF / arbitrary fetch | Host must be `github.com`; fixed API and raw hosts; no user-supplied request targets |
| Imported code | Code execution | Source is parsed as text only; no imports, shells, subprocesses, or evaluation |
| Resource exhaustion | Oversized files/trees | File count, per-file and total byte caps; timeouts; traversal bounds; request-size limits |
| Prompt injection | Repository text steering agents | Untrusted-content framing, bounded context, JSON schema validation, evidence checks, no tools |
| Logs | Secret leakage | Pattern-based redaction for authorization/cookies/keys; tokens never logged |
| MCP | Unauthorised access | Bearer token; same backend ownership checks; read-only by default |
| Supply chain | Vulnerable dependencies | Pinned versions, lockfiles, CI audit workflow (not yet executed in this environment) |

## Implemented controls

### Authentication and sessions

- Argon2id password hashing (`argon2-cffi`), minimum length enforced by schemas.
- Random 256-bit session tokens; only a hash is stored. `HttpOnly`, `SameSite=Lax`, `Path=/`; `Secure`
  in production. TTL configurable (default 7 days).
- CSRF cookie is intentionally readable and paired with `X-CSRF-Token`; mutations without it are
  rejected. Bearer requests skip CSRF because they are not cookie-authenticated.
- Login/register rate limits are separate from the general API limiter. Limits are in-process and
  therefore per-replica; a shared store is required for multi-replica deployment.
- Password change revokes other sessions; logout deletes the session row.
- Account deletion requires the password and the literal confirmation `DELETE`.

### Authorization

- Every repository-scoped endpoint resolves the repository through `owned_repository`.
- Investigations and reports are resolved with the user id, not just the id.
- Agent runs are visible only through investigations the user owns.
- MCP calls carry the same bearer identity, so no separate authorization logic exists.

### Repository ingestion

- `parse_github_url` accepts only `http(s)://(www.)github.com/owner/repo(.git)` and rejects queries,
  fragments, extra path segments, and lookalike hosts.
- Raw content is fetched from `raw.githubusercontent.com` at the snapshot SHA only.
- Files over 256 KiB, more than 400 files, or 20 MiB total are skipped with a reason.
- Binary/ignored/vendored paths are filtered before fetch.
- Imported code is never executed. Parsers only read text.

### AI safety

- Repository content is framed as untrusted data in prompts, with instruction-override warnings.
- Context is bounded (files, characters, symbols).
- Output must validate against `extra="forbid"` Pydantic models; invalid output is rejected.
- Evidence file paths are checked against indexed files; unknown files are removed and issues recorded.
- Agents have no shell, filesystem write, network, or database access beyond their context.
- If no LLM is configured, agents fall back to deterministic analysis and mark AI as unavailable.

### HTTP and logging

- CORS allowlist, credentials enabled, explicit methods and headers.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, HSTS when secure.
- Request size limit, correlation IDs, consistent error bodies without stack traces.
- JSON logs redact authorization headers, cookies and API keys.

### Production guards

Startup fails when `APP_ENV=production` and any of these hold: placeholder/short `APP_SECRET_KEY`,
wildcard CORS origin, or a SQLite database URL. API docs are disabled in production.

## Secrets

- Never commit `.env`; `.env.example` contains placeholders only.
- Personal API tokens are shown once at creation; only a hash and prefix are stored.
- The MCP server reads `NEXUS_API_TOKEN` from its environment; the token is excluded from errors and
  repr output.
- AI keys are read from `AI_API_KEY` server-side and are never sent to the browser.

## Known gaps / unverified

- External container/network hardening and production deployment were not performed; the local
  Docker Compose build and readiness smoke test passed.
- PostgreSQL row-level behaviour and backup/restore were not exercised.
- No external penetration test, ZAP scan, container scan, or Playwright security test was run.
- Rate limiting is single-process; a horizontally scaled deployment needs Redis or a gateway limiter.
- Session fixation relies on rotation at login; review before a public deployment.
- Email verification and password reset require an email provider and are not implemented.
- Private repository access and write actions are deliberately absent.
- Workflow run logs and check annotations are not fetched.
- `pip-audit`/`npm audit` are configured in CI but were not executed in this session; run them before
  deployment.

Report vulnerabilities privately to the maintainer rather than opening a public issue with exploit
details.
