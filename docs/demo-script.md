# Demo script (under 3 minutes)

Use a real indexed repository that you control. The repository should have multiple modules, imports,
tests and at least one risky or complex area. Do not use someone else's production repository without
permission.

> The local `backend/tests/fake_github.py` fixture is for automated tests only; it is not a public
> demo repository. Publish a demo repository or import your own before recording. Nothing in the app
> should be seeded with fake live data.

## 0:00–0:15 — Introduction

Show the dashboard.

"NEXUS is an autonomous engineering intelligence network. It connects real code analysis, a
dependency graph, evidence-backed risk scoring and specialised agents."

Point out that the numbers come from indexed repositories, not a mock.

## 0:15–0:35 — Import

Repositories → paste a public GitHub URL → Import. Show the progress bar and the completed status.
Mention: URL validated, tree fetched at the latest commit, files parsed statically, code never
executed.

## 0:35–0:55 — Code intelligence

Open the repository overview. Show language distribution, file/symbol counts, parser coverage
(`ast` vs `lexer`) and a parser warning. Explain that coverage is reported honestly.

## 0:55–1:15 — Graph

Open Graph. Select a module, show its file and line range. Click **Dependents**, then **Impact**.
Show the affected list and related tests. Explain edge confidence and that impact is reachability,
not severity.

## 1:15–1:35 — Risk

Open Risk center → Run analysis (or show the existing run). Show the overall score, analysis
confidence, available/excluded signals and a finding. Open the finding, show the signal bars and raw
evidence. Say: "This is a prioritisation heuristic, not a probability of failure."

## 1:35–2:10 — Multi-agent investigation

Investigations → ask a realistic question, for example: "Why might the session refresh path lose
authentication state?" Start it. Show the agent timeline (mapper, investigator, risk analyst,
architecture reviewer, planner), the summary, hypotheses with file/line evidence, and the review plan.
Mention the deterministic fallback if no LLM is configured.

## 2:10–2:30 — MCP

In an MCP client (Kiro), call `get_repository_overview` and `get_dependency_chain`. Show the structured
output. Mention the server uses a personal API token and the same ownership checks; writes are gated
behind `NEXUS_MCP_ALLOW_WRITES`.

## 2:30–2:50 — Kiro workflow

Show `.kiro/specs/`, steering documents, a custom agent definition and the MCP configuration. Explain
that specs and acceptance criteria drive the implementation, and that BUILD_STATUS distinguishes
tested from unverified work. Do not show hooks or MCP usage that were not actually run.

## 2:50–3:00 — Close

Show the repository README and, if deployed, the public URL. State the vision: understand a codebase,
investigate with evidence, coordinate agents, and expose the same intelligence through MCP.

## Recording checklist

- [ ] Repository is public or you have permission.
- [ ] Indexing completes before recording.
- [ ] No secrets, tokens or private URLs on screen.
- [ ] Risk analysis exists so the Risk center has evidence.
- [ ] MCP tool calls work from the client; if not, cut that segment rather than simulate it.
- [ ] Video is under three minutes and shows the real application.
