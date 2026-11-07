# Devpost submission guide

## Project

- **Name:** NEXUS — Engineering Intelligence Platform
- **Repository:** https://github.com/MehulBlitz/nexus
- **Demo:** https://nexus-frontend-gbx2.onrender.com/
- **Hackathon:** https://kiroween.devpost.com/

## Short description

NEXUS imports public GitHub repositories, builds an evidence-backed dependency graph, analyzes
release risk, coordinates specialised agents to investigate engineering questions, and exposes the
same intelligence through authenticated MCP tools.

## What to demonstrate

1. Register and sign in.
2. Import `https://github.com/MehulBlitz/nexus`.
3. Wait for indexing to complete.
4. Show Overview, Graph, and Risk.
5. Start an investigation and show the five-agent timeline.
6. Generate a Markdown release report.
7. In Kiro, call `get_repository_overview` and `search_code`.

Use a real indexed repository and do not show tokens, passwords, database URLs, or `.env` files.

## Kiro usage

Kiro steering and specs define the product, architecture, coding, security, and testing workflow.
Kiro MCP was verified against the indexed repository: all seven NEXUS tools completed, including a
five-agent investigation and release report generation. The repository also contains committed Kiro
custom-agent definitions and a hook proposal.

## Technical highlights

- React and TypeScript frontend.
- FastAPI, SQLAlchemy, Alembic, and PostgreSQL backend.
- Python AST analysis plus JavaScript/TypeScript/Java lexer analysis.
- NetworkX dependency graph and transparent heuristic risk scoring.
- Durable database-backed jobs and five specialised agents.
- Authenticated stdio MCP server with read-only defaults and write gating.
- Docker, GitHub Actions, Playwright, and Render HTTPS demo deployment.

## Evidence links

- Playwright: https://github.com/MehulBlitz/nexus/actions/runs/42371333297
- Public demo: https://nexus-frontend-gbx2.onrender.com/
- Build evidence: [BUILD_STATUS.md](../BUILD_STATUS.md)
- Demo script: [demo-script.md](./demo-script.md)

Before submitting, record the public browser flow and a short demo video, verify the official
Devpost eligibility/deadline rules, and complete the form’s required fields.
