# User guide

## Create an account

Open `/register`, enter a display name, email and a password of at least 10 characters. The session
uses an HttpOnly cookie. If you see "session expired", sign in again.

## Import a repository

1. Go to **Repositories**.
2. Paste a public URL such as `https://github.com/owner/repository`.
3. Optionally choose a branch and display name.
4. Select **Import**. NEXUS validates the host, reads metadata and the latest commit, creates a
   snapshot and queues indexing.
5. Watch the progress bar. When status is `indexed`, real file, symbol and graph data is available.
   A malformed source file appears as a parser warning; the job continues.

Only public GitHub repositories are supported. Private repositories and write actions are out of
scope. NEXUS never executes imported code.

## Explore code intelligence

Open the repository **Overview**:

- language distribution and counts
- parser coverage (`ast` for Python, `lexer` for JS/TS/Java) and skip reasons
- parser warnings
- top modules by degree centrality and entry points
- source file table, symbol search and content search (content is fetched from GitHub at the indexed
  commit and is not stored)

## Explore the graph

Open **Graph**:

- Zoom/pan, use the minimap, or **Reset view**.
- Search or filter by node type.
- Click a node to see its source path and line range.
- **Dependencies** / **Dependents** run a bounded traversal and show edge type, depth and confidence.
- **Impact** lists affected nodes, reachability depth and related tests. This is reachability, not a
  severity judgement.
- Edge colours: imports (violet), calls (green), tests (pink), contains (grey), depends-on (amber).

## Review risk

Open **Risk center** and select **Run analysis** if no run exists. You will see:

- overall score, severity and analysis confidence
- severity distribution and the five signals with weights; unavailable signals are marked excluded
- highest-risk modules with the signals used
- findings with severity, score, confidence, recommendations, per-signal bars and raw evidence

Scores are prioritisation heuristics, not probabilities of failure. A finding without evidence should
be treated as unsupported.

## Investigate a problem

Open **Investigations**, enter a question (8+ characters) and optionally a path scope. NEXUS queues a
job and the orchestrator runs five agents in parallel. The detail view shows:

- progress and cancellation while running
- summary, AI status and evidence-verification result
- agent timeline with status, duration and errors
- hypotheses with confidence, reasoning, file/line evidence and suggested checks
- review plan with priority, fix, related files, tests and human-approval flag
- limitations

Without an LLM, deterministic analysis still runs and the UI says AI reasoning was unavailable.

## Generate a report

Open **Reports**, optionally set a title, select **Generate**, then **Download Markdown**. The report
contains repository metadata, language and dependency observations, risk summary, investigation
findings, evidence and limitations. Missing sections are stated as unavailable rather than filled
with invented text.

## Settings

- view profile and provider status
- create/revoke personal API tokens for MCP
- change password (other sessions are revoked)
- delete the account (type `DELETE`; cascades owned data)

## Troubleshooting

| Symptom | Check |
|---|---|
| "API is unreachable" | Backend running on :8000; Vite proxy or nginx `/api` route |
| Import 422 | Use a full `https://github.com/owner/repo` URL |
| Indexing failed | Repository status error; GitHub rate limit or repository size |
| Empty graph | Indexing not finished, or no supported files |
| Investigation failed | Agent errors on the timeline; scope and snapshot |
| MCP "token is not set" | Export `NEXUS_API_TOKEN` before starting the server |
