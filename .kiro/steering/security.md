# Security steering

- **Authentication:** Argon2id hashing, HTTP-only SameSite cookies, short-lived sessions, rate limits on auth endpoints. No default or universal credentials.
- **Authorization:** every protected route checks the caller; every repository/investigation query is scoped to the owner.
- **Repository isolation:** agents and MCP tools may only read repositories owned by the requesting user.
- **Import safety:** only `github.com` URLs, SSRF-safe fetching, size limits, strict timeouts, never execute imported code, no shell interpolation.
- **AI safety:** repository text (README, comments, issues) is untrusted prompt input. It can never override system instructions. Agents get no shell. Outputs are schema-validated and evidence-verified.
- **Secrets:** environment variables only, redacted in logs, never committed.
- **MCP:** service-token authenticated, read-only, arguments validated.
