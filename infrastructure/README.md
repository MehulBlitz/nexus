# Infrastructure

- `../compose.yaml` — PostgreSQL, backend, worker, frontend, optional MCP profile.
- `../backend/Dockerfile` — Python 3.12, non-root user, healthcheck, migrations before uvicorn.
- `../frontend/Dockerfile` — multi-stage Node build served by nginx.
- `../frontend/nginx.conf` — SPA fallback, API proxy, SSE without buffering, security headers.
- `../mcp-server/Dockerfile` — stdio MCP server, non-root user.

Production TLS termination, domain configuration and backups are environment-specific and are
documented in `../docs/deployment.md`. No cloud provider configuration is committed, and no deployment
was performed.
