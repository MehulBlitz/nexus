"""Review Planner: merges agent findings into one prioritised, deduplicated plan."""

from __future__ import annotations

from app.agents.base import Agent
from app.agents.context import AgentContext
from app.agents.schemas import EvidenceRef, PlanItem, PlannerResult

SEVERITY_PRIORITY = {"critical": "P0", "high": "P1", "moderate": "P2", "low": "P3"}


class ReviewPlanner(Agent):
    name = "review_planner"
    title = "Review Planner"
    responsibility = (
        "Combines the investigator, risk and architecture outputs into a prioritised checklist "
        "with evidence, suggested tests and an explicit human-approval requirement."
    )
    output_model = PlannerResult

    def run(self, context: AgentContext) -> PlannerResult:
        prior = context.prior_results
        investigator = prior.get("bug_investigator") or {}
        risk = prior.get("risk_analyst") or {}
        architecture = prior.get("architecture_reviewer") or {}
        limitations: list[str] = []
        items: list[PlanItem] = []
        seen_files: set[str] = set()
        deduped: list[str] = []

        for hypothesis in investigator.get("hypotheses", [])[:3]:
            evidence = hypothesis.get("evidence", [])
            files = [ev["file"] for ev in evidence if ev.get("file")]
            primary = files[0] if files else None
            if primary in seen_files:
                continue
            if primary:
                seen_files.add(primary)
            items.append(
                PlanItem(
                    priority="P1" if hypothesis.get("confidence", 0) >= 0.5 else "P2",
                    problem=f"Verify hypothesis: {hypothesis['title']}",
                    evidence=[
                        EvidenceRef(
                            **{
                                key: ev[key]
                                for key in ("file", "start_line", "end_line")
                                if key in ev
                            }
                        )
                        for ev in evidence[:3]
                    ],
                    suggested_fix=(
                        hypothesis.get("suggested_check")
                        or "Confirm the cited behaviour with a failing test before changing code."
                    ),
                    related_files=files[:5],
                    suggested_tests=[
                        f"Add a regression test covering {primary or 'the affected component'}."
                    ],
                    dependencies=[],
                    complexity="small",
                    requires_human_approval=True,
                )
            )

        for finding in risk.get("findings", [])[:5]:
            file_path = finding.get("file")
            if file_path and file_path in seen_files:
                continue
            if file_path:
                seen_files.add(file_path)
            priority = SEVERITY_PRIORITY.get(finding.get("severity", "low"), "P3")
            items.append(
                PlanItem(
                    priority=priority,
                    problem=(
                        f"{finding['severity'].title()} risk in "
                        f"{file_path or 'repository'}: {finding['title']}"
                    ),
                    evidence=(
                        [
                            EvidenceRef(
                                file=file_path,
                                start_line=1,
                                note=f"risk score {finding['score']}",
                            )
                        ]
                        if file_path
                        else []
                    ),
                    suggested_fix=(
                        "Add focused tests around this module and reduce the signals that drove "
                        "the score before making further changes."
                    ),
                    related_files=[file_path] if file_path else [],
                    suggested_tests=[
                        f"Add a test that imports {file_path} and exercises its main path."
                    ]
                    if file_path
                    else [],
                    dependencies=[],
                    complexity="medium",
                    requires_human_approval=True,
                )
            )

        for observation in architecture.get("observations", [])[:3]:
            if observation.get("severity") in {"high", "moderate"}:
                evidence_files = [ev["file"] for ev in observation.get("evidence", [])]
                items.append(
                    PlanItem(
                        priority="P2",
                        problem=observation["title"],
                        evidence=[
                            EvidenceRef(
                                file=ev["file"],
                                start_line=ev.get("start_line"),
                                end_line=ev.get("end_line"),
                                note=ev.get("note"),
                            )
                            for ev in observation.get("evidence", [])[:3]
                        ],
                        suggested_fix=observation["detail"],
                        related_files=evidence_files,
                        suggested_tests=[
                            "Add an architecture check or test that guards this boundary."
                        ],
                        dependencies=["Coordinate with the module owner."],
                        complexity="large",
                        requires_human_approval=True,
                    )
                )

        for action in investigator.get("recommended_actions", []):
            if action not in deduped:
                deduped.append(action)
        for recommendation in architecture.get("recommendations", []):
            if recommendation not in deduped:
                deduped.append(recommendation)

        if not items:
            limitations.append(
                "No actionable items were produced: the agents found no evidence-linked problems."
            )
        order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        items.sort(key=lambda item: order[item.priority])
        theme = (
            "Prioritised review plan built from investigation evidence, risk findings and "
            "architecture observations."
        )
        return PlannerResult(
            theme=theme,
            items=items,
            deduplicated_recommendations=deduped,
            limitations=limitations,
        )
