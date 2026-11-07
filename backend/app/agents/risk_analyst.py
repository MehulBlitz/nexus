"""Risk Analyst: explains persisted risk findings for the repository."""

from __future__ import annotations

from app.agents.base import Agent
from app.agents.context import AgentContext
from app.agents.schemas import RiskAnalystResult, RiskFindingRef
from app.repositories import analyses as analyses_repo


class RiskAnalyst(Agent):
    name = "risk_analyst"
    title = "Risk Analyst"
    responsibility = (
        "Reads the deterministic risk engine's findings and graph metrics and explains the "
        "highest-risk modules with their measured signals and mitigations."
    )
    output_model = RiskAnalystResult

    def run(self, context: AgentContext) -> RiskAnalystResult:
        run = analyses_repo.latest_completed_run(
            context.session, context.repository.id, "risk"
        )
        if run is None:
            return RiskAnalystResult(
                summary=(
                    "No risk analysis has been completed for this repository, so no risk "
                    "conclusion can be drawn. Run risk analysis first."
                ),
                limitations=["Run POST /repositories/{id}/risks/analyze to produce findings."],
            )
        findings = analyses_repo.findings_for_run(context.session, run.id)
        summary_json = run.summary_json or {}
        refs = [
            RiskFindingRef(
                finding_id=finding.id,
                title=finding.title,
                severity=finding.severity,
                score=round(finding.risk_score, 2),
                confidence=finding.confidence,
                file=finding.file_path,
                why_it_matters=(
                    (finding.recommendations_json or ["Review this module before release."])[0]
                ),
            )
            for finding in findings
        ]
        limitations = list(summary_json.get("limitations") or [])
        if not findings:
            limitations.append(
                "The risk engine found no module above the moderate threshold in this snapshot."
            )
        overall = summary_json.get("overall_score")
        return RiskAnalystResult(
            summary=(
                f"Overall heuristic risk for {context.repository.full_name} is "
                f"{overall if overall is not None else 'not scored'}"
                f"{'/100' if overall is not None else ''} across "
                f"{summary_json.get('module_count', 0)} indexed module(s). "
                f"{len(findings)} module(s) cross the reporting threshold. Scores prioritise "
                "review; they are not failure probabilities."
            ),
            overall_score=overall,
            findings=refs,
            signals_available=list(summary_json.get("signals_available") or []),
            signals_unavailable=list(summary_json.get("signals_missing") or []),
            limitations=limitations,
        )
