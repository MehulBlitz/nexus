"""Investigation orchestration: parallel agents, validation, evidence verification, synthesis.

Each independent agent runs in its own thread with its own database session. Outputs are
validated against Pydantic schemas, then every evidence reference is checked against the
indexed snapshot. Unsupported references are removed and reported, never shown as evidence.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents import AGENT_CLASSES, ReviewPlanner
from app.agents.context import build_context
from app.agents.llm import build_llm
from app.agents.schemas import (
    ArchitectureReviewResult,
    InvestigationResult,
    MapperResult,
    PlannerResult,
    RiskAnalystResult,
)
from app.core.config import get_settings
from app.core.database import get_sessionmaker, utcnow
from app.core.errors import NotFoundError
from app.models.investigation import AgentRun, Investigation
from app.models.repository import Repository, RepositorySnapshot
from app.repositories import code as code_repo
from app.repositories import repos as repos_repo

logger = logging.getLogger("nexus.orchestrator")

AGENT_TIMEOUT_SECONDS = 120
PLANNER_TIMEOUT_SECONDS = 60

OUTPUT_MODELS = {
    "repository_mapper": MapperResult,
    "bug_investigator": InvestigationResult,
    "risk_analyst": RiskAnalystResult,
    "architecture_reviewer": ArchitectureReviewResult,
    "review_planner": PlannerResult,
}


@dataclass
class AgentExecution:
    name: str
    status: str
    output: dict | None
    error: str | None
    elapsed: float


def _mark_investigation_failed(
    session: Session, investigation: Investigation, message: str
) -> None:
    investigation.status = "failed"
    investigation.error_message = message[:2000]
    investigation.completed_at = utcnow()
    session.commit()


def _seed_agent_runs(
    session: Session, investigation: Investigation, names: list[str]
) -> dict[str, AgentRun]:
    records: dict[str, AgentRun] = {}
    for name in names:
        record = AgentRun(
            investigation_id=investigation.id, agent_name=name, status="pending"
        )
        session.add(record)
        records[name] = record
    session.flush()
    session.commit()
    return records


def _run_agent(
    agent_class,
    *,
    repository_id: str,
    question: str,
    scope_path: str | None,
    prior_results: dict,
) -> AgentExecution:
    settings = get_settings()
    llm = build_llm(settings) if agent_class.uses_llm_when_available else None
    started = time.monotonic()
    session = get_sessionmaker()()
    try:
        context = build_context(
            session,
            repository_id=repository_id,
            settings=settings,
            question=question,
            scope_path=scope_path,
            prior_results=prior_results,
            llm=llm,
        )
        output = agent_class().run(context)
        payload = output.model_dump(mode="json")
        return AgentExecution(
            name=agent_class.name,
            status="completed",
            output=payload,
            error=None,
            elapsed=round(time.monotonic() - started, 3),
        )
    except Exception as exc:  # noqa: BLE001 - one agent failing yields partial results
        logger.warning(
            "agent %s failed: %s", agent_class.name, type(exc).__name__, exc_info=True
        )
        return AgentExecution(
            name=agent_class.name,
            status="failed",
            output=None,
            error=f"{type(exc).__name__}: {exc}"[:1000],
            elapsed=round(time.monotonic() - started, 3),
        )
    finally:
        session.close()


def _verify_refs(refs: list[dict], file_lines: dict[str, int]) -> tuple[list[dict], list[str]]:
    verified: list[dict] = []
    issues: list[str] = []
    for ref in refs:
        file = ref.get("file")
        if not file or file not in file_lines:
            issues.append(f"Evidence removed: file is not in the snapshot ({file})")
            continue
        line_count = file_lines[file]
        start = ref.get("start_line")
        end = ref.get("end_line")
        if line_count and start and start > line_count:
            issues.append(f"Evidence line clamped to file length: {file}")
            start = line_count
            end = min(end or line_count, line_count)
        verified.append({**ref, "start_line": start, "end_line": end})
    return verified, issues


def _verify_outputs(outputs: dict[str, dict], file_lines: dict[str, int]) -> tuple[dict, list[str]]:
    issues: list[str] = []
    if "repository_mapper" in outputs:
        mapper = outputs["repository_mapper"]
        mapper["important_files"], mapper_issues = _verify_refs(
            mapper.get("important_files", []), file_lines
        )
        issues.extend(mapper_issues)
    if "bug_investigator" in outputs:
        investigator = outputs["bug_investigator"]
        kept = []
        for hypothesis in investigator.get("hypotheses", []):
            evidence, evidence_issues = _verify_refs(hypothesis.get("evidence", []), file_lines)
            issues.extend(evidence_issues)
            if not evidence:
                issues.append(
                    f"Hypothesis dropped because no evidence could be verified: "
                    f"{hypothesis.get('title', '')[:120]}"
                )
                continue
            kept.append({**hypothesis, "evidence": evidence})
        investigator["hypotheses"] = kept
        if not kept:
            investigator.setdefault("limitations", []).append(
                "No hypothesis survived evidence verification; treat the investigation as "
                "inconclusive."
            )
    if "architecture_reviewer" in outputs:
        architecture = outputs["architecture_reviewer"]
        for observation in architecture.get("observations", []):
            observation["evidence"], observation_issues = _verify_refs(
                observation.get("evidence", []), file_lines
            )
            issues.extend(observation_issues)
    if "review_planner" in outputs:
        planner = outputs["review_planner"]
        for item in planner.get("items", []):
            item["evidence"], planner_issues = _verify_refs(
                item.get("evidence", []), file_lines
            )
            issues.extend(planner_issues)
    if "risk_analyst" in outputs:
        risk = outputs["risk_analyst"]
        for finding in risk.get("findings", []):
            file = finding.get("file")
            if file and file not in file_lines:
                issues.append(f"Risk finding references a file outside the snapshot: {file}")
                finding["file"] = None
    return outputs, issues


def run_investigation(
    session: Session, *, investigation_id: str, progress=None, timeout_seconds: int | None = None
) -> Investigation:
    report = progress or (lambda _p, _m: None)
    investigation = session.get(Investigation, investigation_id)
    if investigation is None:
        raise NotFoundError("Investigation not found")
    repository = session.get(Repository, investigation.repository_id)
    if repository is None:
        _mark_investigation_failed(session, investigation, "Repository no longer exists")
        raise NotFoundError("Repository no longer exists")
    snapshot: RepositorySnapshot | None = repos_repo.latest_snapshot(session, repository.id)
    if snapshot is None:
        _mark_investigation_failed(
            session, investigation, "Repository has no indexed snapshot to investigate"
        )
        return investigation

    investigation.status = "running"
    investigation.started_at = utcnow()
    investigation.snapshot_id = snapshot.id
    investigation.progress = 5
    session.commit()
    report(5, "Selecting agents")

    run_records = _seed_agent_runs(
        session, investigation, [*[c.name for c in AGENT_CLASSES], "review_planner"]
    )
    outputs: dict[str, dict] = {}
    executions: list[AgentExecution] = []
    agent_timeout = timeout_seconds or AGENT_TIMEOUT_SECONDS
    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=len(AGENT_CLASSES)) as pool:
        futures = {
            pool.submit(
                _run_agent,
                agent_class,
                repository_id=repository.id,
                question=investigation.question,
                scope_path=investigation.scope_path,
                prior_results={},
            ): agent_class
            for agent_class in AGENT_CLASSES
        }
        for future, agent_class in futures.items():
            record = run_records[agent_class.name]
            record.status = "running"
            record.started_at = utcnow()
            record.input_json = {
                "question": investigation.question,
                "scope_path": investigation.scope_path,
                "snapshot_id": snapshot.id,
            }
            session.commit()
            remaining = max(1.0, agent_timeout - (time.monotonic() - started))
            try:
                execution = future.result(timeout=remaining)
            except TimeoutError:
                execution = AgentExecution(
                    name=agent_class.name,
                    status="failed",
                    output=None,
                    error=f"Agent exceeded the {agent_timeout}s timeout",
                    elapsed=round(time.monotonic() - started, 3),
                )
            executions.append(execution)
            record.status = execution.status
            record.output_json = execution.output
            record.error_message = execution.error
            record.execution_time = execution.elapsed
            record.completed_at = utcnow()
            if execution.output:
                outputs[execution.name] = execution.output
            session.commit()
            report(
                min(75, 10 + int(60 * len(executions) / len(AGENT_CLASSES))),
                f"{agent_class.title} {execution.status}",
            )

    planner_record = run_records["review_planner"]
    planner_record.status = "running"
    planner_record.started_at = utcnow()
    session.commit()
    prior = {
        name: output
        for name, output in outputs.items()
        if name in {"bug_investigator", "risk_analyst", "architecture_reviewer"}
    }
    planner_execution = _run_agent(
        ReviewPlanner,
        repository_id=repository.id,
        question=investigation.question,
        scope_path=investigation.scope_path,
        prior_results=prior,
    )
    planner_record.status = planner_execution.status
    planner_record.output_json = planner_execution.output
    planner_record.error_message = planner_execution.error
    planner_record.execution_time = planner_execution.elapsed
    planner_record.completed_at = utcnow()
    if planner_execution.output:
        outputs["review_planner"] = planner_execution.output
    executions.append(planner_execution)
    session.commit()
    report(85, "Verifying evidence")

    nodes = code_repo.nodes_for_snapshot(session, snapshot.id, node_types=["file", "test"])
    file_lines = {
        node.file_path: int((node.metadata_json or {}).get("line_count") or 0)
        for node in nodes
        if node.file_path
    }
    outputs, evidence_issues = _verify_outputs(outputs, file_lines)

    investigator_output = outputs.get("bug_investigator") or {}
    planner_output = outputs.get("review_planner") or {}
    limitations = [
        *investigator_output.get("limitations", []),
        *planner_output.get("limitations", []),
        *evidence_issues,
    ]
    failed_agents = [e.name for e in executions if e.status != "completed"]
    if failed_agents:
        limitations.append(
            "These agents did not complete and are excluded from synthesis: "
            + ", ".join(failed_agents)
        )
    ai_used = bool(investigator_output.get("ai_used"))
    if get_settings().ai_provider != "none" and not ai_used:
        limitations.append(
            "An AI provider is configured but no valid AI output was used; results are "
            "deterministic."
        )

    summary = investigator_output.get("summary") or (
        outputs.get("repository_mapper", {}).get("overview")
        or "Investigation completed with partial results."
    )
    result = {
        "summary": summary,
        "question": investigation.question,
        "repository": {"id": repository.id, "full_name": repository.full_name},
        "snapshot": {
            "id": snapshot.id,
            "commit_sha": snapshot.commit_sha,
            "branch": snapshot.branch,
        },
        "hypotheses": investigator_output.get("hypotheses", []),
        "recommended_actions": investigator_output.get("recommended_actions", []),
        "agents": outputs,
        "plan": planner_output.get("items", []),
        "agent_status": [
            {
                "agent": e.name,
                "status": e.status,
                "execution_time": e.elapsed,
                "error": e.error,
            }
            for e in executions
        ],
        "limitations": limitations,
        "ai": {
            "used": ai_used,
            "provider": get_settings().ai_provider,
            "note": (
                "AI reasoning is labelled ai_suggested and evidence-checked."
                if ai_used
                else "Deterministic analysis only; no LLM reasoning was used."
            ),
        },
        "evidence_verification": {
            "files_checked": len(file_lines),
            "issues": evidence_issues[:50],
        },
    }
    evidence_refs = [
        ev
        for hypothesis in result["hypotheses"]
        for ev in hypothesis.get("evidence", [])
    ]
    investigation.status = "completed" if investigator_output or outputs else "failed"
    investigation.progress = 100
    investigation.summary = summary
    investigation.result_json = result
    investigation.evidence_json = {"references": evidence_refs[:50]}
    investigation.ai_used = ai_used
    investigation.completed_at = utcnow()
    if investigation.status == "failed" and not investigation.error_message:
        investigation.error_message = "All agents failed; no result could be produced"
    session.commit()
    report(100, "Investigation complete")
    return investigation
