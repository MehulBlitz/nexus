# Multi-agent orchestration spec

Status: IMPLEMENTED · TESTED against a mocked repository. Ollama/OpenAI-compatible inference was not
available here, so only the deterministic path was exercised.

## Requirements

1. Five specialised agents with distinct responsibilities and strict output schemas.
2. Orchestrator retrieves context, selects agents, runs independent agents in parallel, validates
   outputs, verifies evidence, synthesises and persists results.
3. Per-agent timeouts and bounded retries; a failed non-critical agent must not sink the run.
4. Never fabricate output for an unavailable agent or LLM; label AI as unavailable.
5. Treat repository content as untrusted prompt input; validate all JSON output.
6. Enforce repository ownership and cap context size.
7. Persist every run with status, timing, output or error.

## Acceptance criteria

- [x] Mapper, bug investigator, risk analyst, architecture reviewer and review planner exist.
- [x] Outputs reject unknown fields (`extra="forbid"`).
- [x] Hypothesis evidence must include at least one file reference.
- [x] Evidence references are checked against indexed files; unknown files are dropped/clamped.
- [x] Agent failure is persisted with its error and the run continues.
- [x] LLM absence produces `ai.used=false` with an explicit note.
- [x] Deterministic agents still produce evidence-backed findings.
- [x] Orchestrator terminates within configured limits.
- [ ] Live Ollama inference (no model/server in this environment).

## Design

`app/agents/*`: each class declares `name`, `title`, `responsibility`, `uses_llm_when_available`,
`output_model`, `run(context)`. `app/agents/llm.py` calls Ollama/OpenAI-compatible endpoints with
JSON validation and prompt-injection framing. `app/agents/context.py` builds a bounded snapshot
context. `app/orchestrator/orchestrator.py` runs agents in a thread pool with per-agent DB sessions,
persists `AgentRun`, verifies evidence, and synthesises the final result.

## Data model

`investigations.result_json`, `agent_runs` (agent name, status, input/output JSON, execution time,
error).

## API

`GET /agents`, `GET /agents/runs`, `GET /agents/runs/{id}`, `GET /agents/stats`; investigations API
for execution.

## Tasks

- [x] Agent interface and schemas.
- [x] Five agents.
- [x] Orchestrator with parallelism and timeouts.
- [x] Evidence verification.
- [x] Partial-failure handling.
- [x] Persistence.
- [x] LLM abstraction and deterministic fallback.
- [x] Tests.
- [ ] Optional provider integration test with a real model.

## Tests

Schema rejection tests, evidence requirement, fake-repository orchestration (all agents complete,
evidence files resolve), failure injection (one agent errors, others still complete).
