"""Markdown engineering report generation from persisted, verified data."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.graph.engine import build_view, find_cycles, top_central
from app.models.investigation import Investigation, Report
from app.models.repository import Repository
from app.repositories import analyses as analyses_repo
from app.repositories import code as code_repo
from app.repositories import investigations as inv_repo
from app.repositories import repos as repos_repo
from app.services import risk_engine
from app.services.risk_service import risk_summary


def _timestamp(value) -> str:
    if value is None:
        return "not recorded"
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return str(value)


def _table(rows: list[list[str]], headers: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        cells = [str(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def generate_report(
    session: Session,
    repository: Repository,
    *,
    user_id: str,
    title: str | None = None,
    investigation_id: str | None = None,
) -> Report:
    snapshot = repos_repo.latest_snapshot(session, repository.id)
    if snapshot is None:
        raise ConflictError("Index the repository before generating a report")
    investigation: Investigation | None = None
    if investigation_id:
        investigation = inv_repo.get_owned(session, user_id, investigation_id, repository.id)
        if investigation is None:
            raise NotFoundError("Investigation not found")
        if investigation.status != "completed":
            raise ConflictError("The investigation has not completed yet")

    lines: list[str] = []
    report_title = title or f"Engineering report: {repository.full_name}"
    lines.append(f"# {report_title}")
    lines.append("")
    lines.append(f"Generated {_timestamp(datetime.now(UTC))} by NEXUS.")
    lines.append("")
    lines.append("## Repository")
    lines.append("")
    lines.append(_table([
        ["Repository", repository.full_name],
        ["URL", repository.html_url],
        ["Visibility", repository.visibility],
        ["Branch", snapshot.branch],
        ["Commit", f"`{snapshot.commit_sha}`"],
        ["Snapshot created", _timestamp(snapshot.created_at)],
        ["Indexed files", str(snapshot.file_count)],
        ["Detected symbols", str(snapshot.symbol_count)],
        ["Dependency edges", str(snapshot.edge_count)],
        ["Analysis mode", "Static analysis; no repository code was executed"],
    ], ["Field", "Value"]))
    lines.append("")

    languages = snapshot.languages or {}
    lines.append("## Languages")
    lines.append("")
    lines.append(
        _table(
            [[language, str(count)] for language, count in languages.items()],
            ["Language", "Files"],
        )
    )
    coverage = snapshot.coverage or {}
    parse_modes = coverage.get("parse_modes") or {}
    lines.append("")
    lines.append(
        "Parser coverage: "
        + (", ".join(f"{mode}={count}" for mode, count in parse_modes.items()) or "not recorded")
        + "."
    )
    lines.append("")
    lines.append(
        "> Python is analysed with its standard AST. JavaScript, TypeScript and Java use a "
        "lexer: declarations and imports are reliable, while call edges and end lines are "
        "inferred with lower confidence."
    )
    lines.append("")

    nodes = code_repo.nodes_for_snapshot(session, snapshot.id)
    edges = code_repo.edges_for_snapshot(session, snapshot.id)
    view = build_view(nodes, edges)
    cycles = find_cycles(view, limit=10)
    central = top_central(view, limit=5)
    lines.append("## Dependency observations")
    lines.append("")
    lines.append(_table(
        [[path, f"{degree:.2f}", f"{between:.2f}"] for path, degree, between in central],
        ["Module", "Degree centrality", "Betweenness"],
    ))
    lines.append("")
    if cycles:
        lines.append(f"Detected {len(cycles)} dependency cycle(s) up to depth 8. Cycles involve:")
        for cycle in cycles[:5]:
            names = [
                view.nodes[node_id].file_path or view.nodes[node_id].name
                for node_id in cycle
                if node_id in view.nodes
            ]
            lines.append(f"- {' → '.join(names[:6])}")
    else:
        lines.append("No dependency cycles were detected within the indexed graph.")
    lines.append("")

    summary = risk_summary(session, repository)
    lines.append("## Risk summary")
    lines.append("")
    if summary["analysis_run_id"] is None:
        lines.append("_No risk analysis has been run for this repository._")
    else:
        lines.append(
            f"Overall heuristic score: **{summary['overall_score']}/100** "
            f"({summary['overall_severity']}), computed {_timestamp(summary['analyzed_at'])}. "
            "This is a prioritisation heuristic, not a probability of failure."
        )
        lines.append("")
        counts = summary["severity_counts"]
        lines.append(
            "Severity distribution: "
            + ", ".join(f"{name}={count}" for name, count in counts.items())
            + "."
        )
        lines.append("")
        lines.append(
            "Signals used: "
            + (", ".join(summary["signals_available"]) or "none")
            + ". Unavailable: "
            + (", ".join(summary["signals_unavailable"]) or "none")
            + "."
        )
        if summary["limitations"]:
            lines.append("")
            for limitation in summary["limitations"]:
                lines.append(f"- {limitation}")
        run = analyses_repo.latest_completed_run(session, repository.id, "risk")
        if run is not None:
            findings = analyses_repo.findings_for_run(session, run.id)
            lines.append("")
            lines.append("### Top risk findings")
            lines.append("")
            rows = []
            for finding in findings[:10]:
                rows.append([
                    finding.file_path or "repository",
                    finding.severity,
                    f"{finding.risk_score:.1f}",
                    f"{finding.confidence:.2f}",
                    (finding.recommendations_json or ["Review"])[0],
                ])
            lines.append(_table(rows, ["Module", "Severity", "Score", "Confidence", "Mitigation"]))
            if findings:
                lines.append("")
                lines.append(
                    "Evidence for the highest finding: `"
                    + str((findings[0].evidence_json or {}).get("signals"))
                    + "` using weights "
                    + str(risk_engine.DEFAULT_WEIGHTS)
                    + "."
                )
    lines.append("")

    if investigation is not None:
        result = investigation.result_json or {}
        lines.append("## Investigation")
        lines.append("")
        lines.append(f"**Question:** {investigation.question}")
        lines.append("")
        lines.append(investigation.summary or "_No summary recorded._")
        lines.append("")
        hypotheses = result.get("hypotheses") or []
        if hypotheses:
            lines.append("### Hypotheses")
            for hypothesis in hypotheses:
                lines.append("")
                lines.append(
                    f"- **{hypothesis.get('title')}** (confidence {hypothesis.get('confidence')}, "
                    f"origin {hypothesis.get('origin', 'inferred')})"
                )
                lines.append(f"  - {hypothesis.get('reasoning', '')}")
                for evidence in hypothesis.get("evidence", []):
                    lines.append(
                        f"  - Evidence: `{evidence.get('file')}` lines "
                        f"{evidence.get('start_line')}–{evidence.get('end_line')}"
                    )
        plan = result.get("plan") or []
        if plan:
            lines.append("")
            lines.append("### Recommended plan")
            lines.append("")
            lines.append(_table(
                [
                    [
                        item.get("priority", ""),
                        item.get("problem", ""),
                        ", ".join(item.get("related_files") or []) or "—",
                        "yes" if item.get("requires_human_approval") else "no",
                    ]
                    for item in plan[:10]
                ],
                ["Priority", "Problem", "Files", "Human approval"],
            ))
        for limitation in result.get("limitations") or []:
            lines.append(f"- Limitation: {limitation}")
        lines.append("")

    lines.append("## Methodology and limitations")
    lines.append("")
    lines.append(
        "- Risk scores are prioritisation heuristics, not a probability of failure.\n"
        "- Repository content was parsed as untrusted text and never executed.\n"
        "- Only source locations that exist in the indexed snapshot are cited.\n"
        "- Import and call relationships carry confidence values; inferred edges are labelled.\n"
        "- GitHub change history is optional; when unavailable, risk weights are renormalised "
        "instead of inventing values."
    )
    if snapshot.warnings:
        lines.append("")
        lines.append("### Indexing warnings")
        for warning in snapshot.warnings[:10]:
            lines.append(f"- {warning}")

    report = inv_repo.create_report(
        session,
        repository_id=repository.id,
        user_id=user_id,
        snapshot_id=snapshot.id,
        title=report_title,
        markdown="\n".join(lines),
    )
    session.commit()
    return report
