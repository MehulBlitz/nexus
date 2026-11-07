# Authentication spec

Status: IMPLEMENTED · TESTED (15 auth tests plus integration authorization checks).

## Requirements

1. Register, log in, log out, refresh, and read the current user.
2. Hash passwords with Argon2id; never store or log plaintext.
3. Prefer HTTP-only, SameSite cookies over browser-readable tokens.
4. Require a CSRF token on cookie-authenticated mutations (double-submit).
5. Rate-limit authentication endpoints.
6. Enforce per-user ownership on every repository-scoped endpoint.
7. Support account deletion and personal API tokens for MCP/scripts.
8. No universal default password and no publicly reachable admin account.
9. Development mode must be explicitly labelled; production rules are stricter.

## Acceptance criteria

- [x] A second user receives 404 for another user's repository, investigation, report and graph.
- [x] Cookies are HttpOnly (session) and SameSite=Lax; CSRF cookie is readable by design.
- [x] Mutations without `X-CSRF-Token` are rejected for cookie sessions.
- [x] Bearer tokens authenticate API requests without a CSRF header.
- [x] Logout clears cookies and revokes the session row.
- [x] Password change revokes other sessions.
- [x] Account deletion removes owned data via cascades.
- [x] Audit events record login, token creation and destructive actions.

## Design

- `app/core/security.py`: Argon2id hashing, opaque session token generation (`secrets`), token hashing
  for API tokens (only a prefix and hash are stored).
- `app/api/v1/auth.py`: register/login/refresh/logout/me/change-password/account/tokens.
- `app/api/deps.py`: `current_user` resolves bearer token or session cookie; `require_csrf` checks the
  double-submit token and same-origin request for cookie authentication.
- `app/services/rate_limit.py`: in-process sliding window, documented as single-process only.
- Session records store expiry, user agent and a hash; cookies carry the opaque value only.

## Data model

`users`, `user_sessions`, `api_tokens`, `account_deletions`, `audit_events`. Tokens store a hash and
prefix, never the plaintext. Timestamps are UTC.

## API

`POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`,
`GET /auth/me`, `POST /auth/change-password`, `POST /auth/account`,
`GET|POST|DELETE /auth/tokens`.

## Tasks

- [x] User model and migration.
- [x] Argon2id hashing and password policy.
- [x] Session cookies, refresh and logout.
- [x] CSRF and origin checks.
- [x] Rate limits.
- [x] API tokens.
- [x] Account deletion.
- [x] Audit events.
- [x] Tests.
- [ ] Email verification (requires a real email provider; not configured).

## Tests

Unit: hashing, token parsing, rate limit, CSRF rejection. Integration: register/login/logout,
refresh, authorization boundaries, token auth, deletion.
