# NEXUS

**Autonomous Engineering Intelligence Network**

Understand a codebase. Investigate problems with evidence. See engineering risk and the signals
behind it. Coordinate specialised agents. Reach the same intelligence through MCP.

> **Status: Core Release 1 implemented and locally tested.** Backend, frontend and MCP test suites
> pass; the production frontend builds. Docker/Compose and PostgreSQL were **not** run in the
> authoring environment, and no public deployment exists. See [BUILD_STATUS.md](BUILD_STATUS.md) for
> the exact evidence and every unverified item.

![Landing page](docs/screenshots/landing.png)

## The problem

Repository knowledge is scattered across source files, imports, tests, commits, pull requests, issues
and CI. Understanding the consequences of a change or investigating a bug means manually collecting
context from several tools.

## The solution

NEXUS imports a real public GitHub repository, parses it statically, builds a dependency graph, scores
transparent risk signals, and investigates questions with specialised agents. Findings cite the file
and line they come from, and unavailable data is labelled as unavailable.

## Features

- **Authentication** — Argon2id, HttpOnly session cookies, CSRF, rate limits, API tokens, account
  deletion, audit events.
- **Public GitHub import** — strict URL validation, tree and raw-file fetch at a snapshot commit,
  size/binary filtering, progress and retry state.
- **Code intelligence** — Python AST; documented lexer for JavaScript, TypeScript and Java. Files,
  modules, classes, functions, imports, calls, line ranges and parser warnings.
- **Knowledge graph** — directed graph with evidence and confidence; bounded traversal, reverse
  traversal, cycles, components, centrality and impact analysis.
- **Risk engine** — weighted signals (centrality, complexity, change frequency, test presence, recent
  activity), normalised, missing signals excluded and weights renormalised.
- **Five agents** — mapper, bug investigator, risk analyst, architecture reviewer, review planner,
  each with a strict output schema and evidence requirements.
- **Investigations** — async jobs, parallel agents, agent timeline, SSE/polling, hypotheses,
  actionable plan, limitations and AI-availability reporting.
- **GitHub activity** — commits, pull requests, issues and workflow runs, with explicit unavailable
  reasons.
- **Reports** — Markdown engineering report with risk, dependency observations, investigation
  findings, evidence and limitations.
- **MCP server** — seven tools over authenticated HTTP; read-only by default.
- **Kiro artifacts** — steering, specs, four custom agent roles and a hook proposal, all committed.

## Screenshots

| Dashboard |
|---|
| ![Dashboard](docs/screenshots/dashboard.png) |

These are captures of the running local application. The dashboard is shown empty because screenshots
were taken without importing a real repository; it does not contain seeded or fabricated data.

## Architecture

```text
React + TypeScript ──REST/SSE──┐
                               ├──> FastAPI /api/v1 ──> PostgreSQL / SQLite
MCP client ──stdio──> nexus_mcp┘         │
                                         ├──> durable jobs table ──> worker
                                         │        ├── GitHub adapter
                                         │        ├── AST/lexer parsers
                                         │        └── graph engine
                                         └──> orchestrator ──> 5 agents
                                                   └── evidence verification
```

Details and design decisions: [docs/architecture.md](docs/architecture.md). Security threat model:
[docs/security.md](docs/security.md). API: [docs/api.md](docs/api.md).

## Technology

**Frontend:** React 18, TypeScript strict, Vite 6, Tailwind CSS 4, React Router, TanStack Query,
Zustand, React Flow (`@xyflow/react`), Recharts, Zod, Lucide.
**Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Argon2id, NetworkX, HTTPX.
**Data:** PostgreSQL in production; SQLite for development/tests.
**AI:** optional Ollama or OpenAI-compatible endpoint; deterministic fallback is mandatory.
**MCP:** official Python MCP SDK (v1 and v2 server APIs supported).
**Tests:** Pytest, Hypothesis, Vitest, React Testing Library, Playwright configuration, Ruff, ESLint.

## Repository layout

```text
.kiro/          steering, 12 specs, 4 custom agents, hook proposal
backend/        FastAPI app, analyzers, graph, agents, orchestrator, migrations, tests
frontend/       React command center, graph explorer, tests
mcp-server/     authenticated MCP tools and tests
shared/         API example payloads and contract notes
infrastructure/ deployment asset notes
docs/           architecture, API, security, deployment, MCP, user guide, demo script
.github/        CI and security workflows
compose.yaml    local stack definition
```

## Quick start (no Docker)

Prerequisites: Python 3.12+, Node 22+.

```bash
cp .env.example .env
# For local SQLite set: DATABASE_URL=sqlite:///./nexus_dev.sqlite3 and JOB_EXECUTION_MODE=inline

cd backend
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

Register, open **Repositories**, and import a public GitHub repository such as
`https://github.com/owner/repository`. Indexing progress is shown; analysis is snapshot-scoped.

## Docker

```bash
cp .env.example .env     # replace every placeholder
docker compose up --build
```

Services: PostgreSQL, backend (migrations + API), worker, frontend (nginx). Optional MCP profile:

```bash
docker compose --profile mcp run --rm mcp
```

> The Compose stack has **not been built or run** here. Treat it as configuration awaiting
> verification, not as a tested deployment.

## Migrations

```bash
cd backend
python -m alembic upgrade head
python -m alembic downgrade -1
```

The initial migration creates 16 tables and indexes. It was exercised on SQLite (upgrade, downgrade,
upgrade); PostgreSQL execution is unverified.

## Tests and checks

```bash
make backend-lint backend-test          # Ruff + 115 Pytest tests
make frontend-check frontend-test       # tsc, ESLint, 9 Vitest tests
make frontend-build                     # production Vite build
make mcp-lint mcp-test                  # Ruff + 11 MCP tests
make check                              # all of the above
```

Backend integration tests use a mocked GitHub transport; they exercise the real service, parser,
graph, risk, agent and report layers. No test requires a paid AI key. Playwright configuration is
present, but browsers were not installed and the E2E scenario was not executed.

## MCP

Create a personal API token in **Settings → API tokens**, then configure an MCP client:

```json
{
  "mcpServers": {
    "nexus": {
      "command": "python",
      "args": ["-m", "nexus_mcp.server"],
      "env": {
        "NEXUS_API_URL": "http://localhost:8000",
        "NEXUS_API_TOKEN": "paste-token-here"
      }
    }
  }
}
```

Tools: `get_repository_overview`, `search_code`, `get_dependency_chain`, `analyze_release_risk`,
`investigate_issue`, `get_agent_status`, `generate_release_report`. The last two are write-capable and
disabled unless `NEXUS_MCP_ALLOW_WRITES=1`. Setup: [docs/mcp-setup.md](docs/mcp-setup.md).

## Kiro workflow

Committed in `.kiro/`:

- **Steering:** product, architecture, coding standards, security, testing.
- **Specs:** foundation (requirements/design/tasks) plus authentication, repository ingestion, code
  intelligence, knowledge graph, risk analysis, multi-agent, investigation, GitHub integration, MCP,
  frontend, deployment/security. Each contains requirements, acceptance criteria, design, contracts,
  tasks and test requirements.
- **Custom agents:** architecture reviewer, security reviewer, test engineer, documentation engineer.
- **Hooks:** proposal in `.kiro/hooks/README.md`; not installed because no Kiro UI session was
  available.
- **Usage log:** [docs/kiro-development-log.md](docs/kiro-development-log.md), with unperformed items
  marked explicitly.

Kiro was not available in the authoring environment, so running Kiro agents/hooks or connecting Kiro
to MCP is not claimed. The artifacts and the MCP server are ready for that verification.

## Evidence policy

- Static analysis only; imported code is never executed.
- Actual, inferred and AI-suggested content are labelled; inferred edges carry confidence.
- Every hypothesis requires a file reference, verified against indexed nodes.
- Missing risk signals are excluded, not replaced; confidence reflects available weight.
- Activity sections state when GitHub data is unavailable or permission-restricted.
- Heuristic risk scores are never described as failure probabilities.

## Security

Implemented: Argon2id, HttpOnly/SameSite cookies, CSRF double-submit, origin checks, rate limits,
ownership enforcement, SSRF-safe GitHub parsing, file/byte caps, prompt-injection framing, strict
output validation, evidence checks, secret redaction, production config guards, bearer-token MCP.

Not performed: Docker/network hardening, external penetration test, container scan, PostgreSQL
verification, public HTTPS deployment. Do not treat this build as production-verified. See
[docs/security.md](docs/security.md).

## Known limitations

- Docker/Compose and PostgreSQL are unverified; Redis/RQ is not used (durable DB queue instead).
- Python 3.15 has no `tree-sitter` wheel; JS/TS/Java use a lexer with honest coverage reporting.
- Java support is basic; no type resolution or cross-file call graph beyond imports.
- Rate limits and SSE are in-process; multi-replica deployment needs shared infrastructure.
- Email verification, password reset, private repositories and write actions are absent.
- Risk weights are documented assumptions, not calibrated probabilities.
- Live GitHub import and live MCP/Kiro calls were not verified in this environment.
- Playwright E2E was not run; screenshots cover the landing, dashboard and repository page only.
- Video, public URL and Devpost submission are outside this build.

## Roadmap

1. Verify Compose and PostgreSQL; add backup/restore drill to CI or a staging runbook.
2. Optional tree-sitter analyzers when wheels are available; richer Java/cross-file resolution.
3. Shared rate-limit store and horizontally scalable workers.
4. GitHub App/OAuth for private repositories with a security review.
5. Calibrate risk weights and add trend analysis across snapshots.
6. Playwright E2E and accessibility checks in CI.
7. Public demo deployment and a three-minute recording.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Never commit secrets; never remove `.kiro/`; update
`BUILD_STATUS.md` with evidence, not optimism.

## License

MIT — see [LICENSE](LICENSE).
