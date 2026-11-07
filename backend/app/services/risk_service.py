"""Repository-wide risk analysis producing persisted, evidence-backed findings."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import ensure_utc, utcnow
from app.core.errors import ConflictError
from app.graph.engine import build_view
from app.integrations.github import GitHubClient
from app.models.analysis import AnalysisRun
from app.models.repository import Repository
from app.repositories import analyses as analyses_repo
from app.repositories import code as code_repo
from app.repositories import repos as repos_repo
from app.services import risk_engine
from app.services.github_service import build_client

logger = logging.getLogger("nexus.risk")

MAX_HISTORY_COMMITS = 20
MAX_COMMIT_DETAILS = 8


def _file_metrics(session: Session, snapshot_id: str) -> dict[str, dict]:
    nodes = code_repo.nodes_for_snapshot(session, snapshot_id, node_types=["file", "test"])
    edges = code_repo.edges_for_snapshot(session, snapshot_id)
    view = build_view(nodes, edges)
    degree = dict(view.graph.in_degree())
    metrics: dict[str, dict] = {}
    for node in nodes:
        if not node.file_path:
            continue
        metadata = node.metadata_json or {}
        metrics[node.file_path] = {
            "node_id": node.id,
            "path": node.file_path,
            "language": node.language,
            "line_count": int(metadata.get("line_count") or 0),
            "complexity": float(metadata.get("complexity") or 1),
            "imports": int(metadata.get("import_count") or 0),
            "in_degree": int(degree.get(node.id, 0)),
            "is_test": node.node_type == "test",
            "imported_by_test": False,
            "warnings": metadata.get("warnings") or [],
        }
    for edge in edges:
        if edge.relationship_type not in {"TESTS", "IMPORTS"}:
            continue
        source = view.nodes.get(edge.source_node_id)
        target = view.nodes.get(edge.target_node_id)
        if (
            source
            and target
            and source.node_type == "test"
            and target.file_path
            and target.file_path in metrics
        ):
            metrics[target.file_path]["imported_by_test"] = True
    return metrics


def fetch_change_history(
    repository: Repository, *, client: GitHubClient, branch: str | None = None
) -> dict:
    """Bounded change history: recent commits and a few per-commit file lists.

    Returns available=False with a reason when GitHub cannot supply the data, so the risk
    engine can mark the signal unavailable instead of guessing.
    """
    parts = repository.full_name.split("/")
    if len(parts) != 2:
        return {"available": False, "reason": "Invalid repository name", "files": {}}
    ref = type("Ref", (), {"owner": parts[0], "repo": parts[1]})()
    commits = client.list_commits(
        ref, branch or repository.default_branch, limit=MAX_HISTORY_COMMITS
    )
    if not commits.available:
        return {"available": False, "reason": commits.reason or "Commits unavailable", "files": {}}
    per_file: dict[str, dict] = {}
    details_fetched = 0
    for commit in commits.items[:MAX_COMMIT_DETAILS]:
        try:
            detail = client._request(  # noqa: SLF001 - adapter-level detail fetch
                f"/repos/{ref.owner}/{ref.repo}/commits/{commit['sha']}"
            )
        except Exception:  # noqa: BLE001 - partial history is still useful
            break
        details_fetched += 1
        date = (detail.get("commit") or {}).get("author", {}).get("date")
        for file_info in detail.get("files") or []:
            path = file_info.get("filename")
            if not isinstance(path, str):
                continue
            entry = per_file.setdefault(path, {"commits": 0, "last_change": None})
            entry["commits"] += 1
            if date:
                entry["last_change"] = date
    if details_fetched == 0:
        return {
            "available": False,
            "reason": "GitHub did not return commit details for this repository",
            "files": {},
        }
    return {
        "available": True,
        "reason": None,
        "files": per_file,
        "commits_scanned": details_fetched,
    }


def _days_since(iso_value: str | None) -> float | None:
    if not iso_value:
        return None
    try:
        moment = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (utcnow() - ensure_utc(moment)).total_seconds() / 86400)


def analyze_repository_risk(
    session: Session,
    repository: Repository,
    *,
    user_id: str,
    include_github_history: bool = True,
    max_findings: int = 25,
    progress=None,
    settings: Settings | None = None,
    client: GitHubClient | None = None,
) -> AnalysisRun:
    settings = settings or get_settings()
    report = progress or (lambda _p, _m: None)
    snapshot = repos_repo.latest_snapshot(session, repository.id)
    if snapshot is None:
        raise ConflictError("Index this repository before analysing risk")
    existing = analyses_repo.latest_completed_run(session, repository.id, "risk")
    run = analyses_repo.create_run(
        session,
        repository_id=repository.id,
        user_id=user_id,
        analysis_type="risk",
        snapshot_id=snapshot.id,
        params={
            "include_github_history": include_github_history,
            "max_findings": max_findings,
            "weights": risk_engine.DEFAULT_WEIGHTS,
        },
    )
    run.status = "running"
    run.started_at = utcnow()
    session.commit()
    report(10, "Collecting file metrics")

    metrics = _file_metrics(session, snapshot.id)
    history = {"available": False, "reason": "Not requested", "files": {}}
    if include_github_history and metrics:
        owns_client = client is None
        github = client or build_client(settings)
        try:
            report(25, "Reading recent GitHub history")
            history = fetch_change_history(repository, client=github, branch=snapshot.branch)
        finally:
            if owns_client:
                github.close()
    report(45, "Scoring modules")

    max_complexity = max((m["complexity"] for m in metrics.values()), default=0.0)
    max_commits = max(
        (history["files"].get(path, {}).get("commits", 0) for path in metrics), default=0
    )
    scored: list[dict] = []
    for path, metric in metrics.items():
        history_entry = history["files"].get(path, {}) if history["available"] else {}
        signals = {
            "dependency_centrality": risk_engine.normalise_relative(
                metric["in_degree"], max((m["in_degree"] for m in metrics.values()), default=0)
            ),
            "code_complexity": risk_engine.normalise_log(metric["complexity"], max_complexity),
            "change_frequency": (
                risk_engine.normalise_relative(history_entry.get("commits", 0), max_commits)
                if history["available"]
                else None
            ),
            "test_presence": risk_engine.test_presence_signal(
                is_test=metric["is_test"], imported_by_test=metric["imported_by_test"]
            ),
            "recent_change_activity": (
                risk_engine.recency_signal(_days_since(history_entry.get("last_change")))
                if history["available"] and history_entry
                else None
            ),
        }
        result = risk_engine.compute_risk(signals)
        scored.append(
            {
                **metric,
                "signals": signals,
                "score": result.score,
                "severity": result.severity,
                "confidence": result.confidence,
                "used_signals": result.used_signals,
                "missing_signals": result.missing_signals,
            }
        )
    scored.sort(key=lambda item: (item["score"], item["in_degree"]), reverse=True)
    report(70, "Writing findings")

    severity_counts = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for item in scored:
        if item["severity"] in severity_counts:
            severity_counts[item["severity"]] += 1

    from app.models.analysis import Finding

    for item in scored[:max_findings]:
        if item["score"] < 25:
            continue
        recommendations = _recommendations(item)
        session.add(
            Finding(
                analysis_run_id=run.id,
                repository_id=repository.id,
                snapshot_id=snapshot.id,
                finding_type="module_risk",
                severity=item["severity"],
                title=f"{item['path']} ({item['severity']} risk)",
                description=(
                    f"Weighted heuristic risk score {item['score']:.1f}/100 for {item['path']}. "
                    f"Score uses {len(item['used_signals'])} available signal(s); "
                    f"{', '.join(item['missing_signals']) or 'no'} signal(s) unavailable."
                ),
                risk_score=item["score"],
                confidence=item["confidence"],
                origin="measured",
                file_path=item["path"],
                evidence_json={
                    "signals": item["signals"],
                    "used_signals": item["used_signals"],
                    "missing_signals": item["missing_signals"],
                    "line_count": item["line_count"],
                    "complexity": item["complexity"],
                    "incoming_dependencies": item["in_degree"],
                    "is_test": item["is_test"],
                    "imported_by_test": item["imported_by_test"],
                    "parser_warnings": item["warnings"],
                    "weights": risk_engine.DEFAULT_WEIGHTS,
                    "history_available": history["available"],
                    "history_reason": history["reason"],
                    "method": "weighted average over available, normalised signals",
                },
                recommendations_json=recommendations,
            )
        )

    overall_values = [item["score"] for item in scored if item["score"] > 0]
    overall = round(sum(overall_values) / len(overall_values), 2) if overall_values else 0.0
    signals_available = sorted(
        {
            signal
            for item in scored
            for signal, value in item["signals"].items()
            if value is not None
        }
    )
    signals_missing = sorted(
        {
            signal
            for item in scored
            for signal, value in item["signals"].items()
            if value is None
        }
    )
    limitations = [
        "Scores are heuristics for prioritisation, not probabilities of failure.",
        "Test presence is used because coverage data is not available from static analysis.",
    ]
    if not history["available"]:
        limitations.append(
            f"GitHub change history unavailable: {history['reason']}. "
            "Change frequency and recent activity were excluded and weights renormalised."
        )
    run.status = "completed"
    run.progress = 100
    run.completed_at = utcnow()
    run.summary_json = {
        "overall_score": overall,
        "overall_severity": risk_engine.classify(overall),
        "severity_counts": severity_counts,
        "module_count": len(scored),
        "signals_available": signals_available,
        "signals_missing": signals_missing,
        "history_available": history["available"],
        "history_reason": history["reason"],
        "previous_run_id": existing.id if existing else None,
        "weights": risk_engine.DEFAULT_WEIGHTS,
        "limitations": limitations,
        "classified_modules": [
            {
                "path": item["path"],
                "score": item["score"],
                "severity": item["severity"],
                "confidence": item["confidence"],
                "used_signals": item["used_signals"],
            }
            for item in scored[:25]
        ],
    }
    session.commit()
    report(100, "Risk analysis complete")
    return run


def _recommendations(item: dict) -> list[str]:
    recommendations: list[str] = []
    if item["is_test"]:
        return ["Test file: risk here is informational; keep it maintainable."]
    if not item["imported_by_test"]:
        recommendations.append("Add or connect a test that imports this module.")
    if item["in_degree"] >= 3:
        recommendations.append(
            "This module has several dependents: review changes here before release."
        )
    if item["complexity"] >= 10:
        recommendations.append("Consider splitting complex functions and adding focused tests.")
    if not recommendations:
        recommendations.append("No urgent action; keep monitoring after changes.")
    return recommendations


def risk_summary(session: Session, repository: Repository) -> dict:
    run = analyses_repo.latest_completed_run(session, repository.id, "risk")
    if run is None:
        return {
            "repository_id": repository.id,
            "snapshot_id": None,
            "analysis_run_id": None,
            "overall_score": None,
            "overall_severity": None,
            "analyzed_at": None,
            "module_count": 0,
            "severity_counts": {"low": 0, "moderate": 0, "high": 0, "critical": 0},
            "signals_available": [],
            "signals_unavailable": [],
            "weights": risk_engine.DEFAULT_WEIGHTS,
            "classified_modules": [],
            "confidence": 0.0,
            "limitations": ["No risk analysis has run for this repository yet."],
        }
    summary = run.summary_json or {}
    counts = summary.get("severity_counts") or {}
    return {
        "repository_id": repository.id,
        "snapshot_id": run.snapshot_id,
        "analysis_run_id": run.id,
        "overall_score": summary.get("overall_score"),
        "overall_severity": summary.get("overall_severity"),
        "analyzed_at": run.completed_at,
        "module_count": summary.get("module_count", 0),
        "severity_counts": {
            "low": counts.get("low", 0),
            "moderate": counts.get("moderate", 0),
            "high": counts.get("high", 0),
            "critical": counts.get("critical", 0),
        },
        "signals_available": summary.get("signals_available", []),
        "signals_unavailable": summary.get("signals_missing", []),
        "weights": summary.get("weights", risk_engine.DEFAULT_WEIGHTS),
        "classified_modules": summary.get("classified_modules", []),
        "confidence": round(
            len(summary.get("signals_available", [])) / len(risk_engine.DEFAULT_WEIGHTS), 3
        )
        if summary
        else 0.0,
        "limitations": summary.get("limitations", []),
    }
