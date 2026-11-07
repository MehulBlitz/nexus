# NEXUS product steering

## Vision
NEXUS is an engineering intelligence platform. It unifies repositories, dependency structure, risk signals and specialised agents so developers can investigate problems without collecting context from many tools.

## Users
Individual developers, students, teams, technical leads, engineering managers, open-source maintainers.

## Main workflows
1. Import a public GitHub repository and index it.
2. Explore the dependency graph and run impact analysis.
3. Review evidence-backed risk findings.
4. Ask an investigation question and read a structured, evidence-cited report.
5. Export a Markdown report.
6. Reach the same intelligence through MCP tools (read-only).

## Scope (Core Release 1)
Auth, public GitHub import, indexing, Python and JS/TS parsing, graph, risk engine, at least three distinct agents, investigations, reports, MCP server with at least three tools, Docker deployment, tests, README.

## Non-goals
- Executing code from imported repositories.
- Private-repository access until a GitHub App or OAuth flow is built and security-tested.
- Requiring a paid AI API or sending private source to an external model.
- Presenting heuristic scores as failure probabilities.

## Acceptance rules
- Every finding states what, where, why, evidence, confidence and next step.
- Findings are labelled actual, inferred or AI-suggested.
- Unavailable data is shown as unavailable, never fabricated.
- A feature is not done because its UI exists; it needs passing tests.
