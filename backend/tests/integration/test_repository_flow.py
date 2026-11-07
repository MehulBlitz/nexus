"""End-to-end backend flow: import, index, explore, analyse risk, investigate, report."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_sessionmaker
from app.models.job import Job
from app.services import job_service
from tests.conftest import register
from tests.fake_github import build_test_client


@pytest.fixture
def fake_github(monkeypatch):
    def factory(_settings=None):
        return build_test_client()

    monkeypatch.setattr("app.services.github_service.build_client", factory)
    monkeypatch.setattr("app.services.indexing_service.build_client", factory)
    monkeypatch.setattr("app.services.risk_service.build_client", factory)
    monkeypatch.setattr("app.services.search_service.build_client", factory)
    return factory


@pytest.fixture
def indexed(auth_client, fake_github):
    response = auth_client.post(
        "/api/v1/repositories", json={"url": "https://github.com/acme/demo"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["active_job"], "import must queue an indexing job"
    job_service.execute_job(body["active_job"]["id"])
    status = auth_client.get(f"/api/v1/repositories/{body['id']}/status").json()
    assert status["status"] == "indexed", status
    return body["id"]


def test_import_requires_a_valid_github_url(auth_client):
    for url in [
        "https://gitlab.com/a/b",
        "not-a-url",
        "https://github.com/only-owner",
        "http://github.com/acme/demo",
    ]:
        response = auth_client.post("/api/v1/repositories", json={"url": url})
        assert response.status_code == 422, url
        # Short strings fail schema validation; valid-looking non-GitHub URLs fail the adapter.
        assert response.json()["error"]["code"] in {"unprocessable", "validation_error"}


def test_worker_claimed_job_is_executed(auth_client, fake_github):
    response = auth_client.post(
        "/api/v1/repositories", json={"url": "https://github.com/acme/demo"}
    )
    assert response.status_code == 201
    job_id = response.json()["active_job"]["id"]

    with get_sessionmaker()() as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.status = "RUNNING"
        session.commit()

    job_service.execute_job(job_id)

    with get_sessionmaker()() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "COMPLETED"


def test_indexing_produces_real_code_intelligence(indexed, auth_client):
    overview = auth_client.get(f"/api/v1/repositories/{indexed}/overview").json()
    assert overview["file_count"] >= 6
    assert overview["snapshot"]["commit_sha"] == "a" * 40
    languages = {item["language"]: item["files"] for item in overview["languages"]}
    assert languages["Python"] >= 4
    assert languages["TypeScript"] >= 1  # lib/api.ts and web/store.ts
    assert overview["symbol_count"] >= 4
    assert overview["parser_coverage"]["parse_modes"]["ast"] >= 4
    assert overview["parser_coverage"]["parse_modes"]["lexer"] >= 2
    warnings = " ".join(overview["warnings"])
    assert "app/broken.py" in warnings  # malformed file is a warning, not a crash
    assert overview["test_file_count"] >= 1

    files = auth_client.get(f"/api/v1/repositories/{indexed}/files").json()
    paths = {item["path"] for item in files["items"]}
    assert {"app/auth.py", "app/session.py", "web/store.ts", "tests/test_auth.py"} <= paths

    symbols = auth_client.get(
        f"/api/v1/repositories/{indexed}/symbols", params={"q": "refresh_session"}
    ).json()
    assert symbols["total"] >= 1
    assert symbols["items"][0]["file_path"] == "app/auth.py"


def test_graph_traversal_and_impact(indexed, auth_client):
    graph = auth_client.get(f"/api/v1/repositories/{indexed}/graph").json()
    assert graph["node_total"] > 5
    assert any(edge["relationship_type"] == "IMPORTS" for edge in graph["edges"])
    assert all(edge["confidence"] <= 1.0 for edge in graph["edges"])

    files = auth_client.get(f"/api/v1/repositories/{indexed}/files").json()["items"]
    by_path = {item["path"]: item["node_id"] for item in files}
    auth_id = by_path["app/auth.py"]

    chain = auth_client.get(
        f"/api/v1/repositories/{indexed}/graph/dependencies/{by_path['app/session.py']}",
        params={"direction": "dependents", "max_depth": 3},
    ).json()
    assert chain["steps"]
    assert any(step["node"]["file_path"] == "app/auth.py" for step in chain["steps"])

    impact = auth_client.post(
        f"/api/v1/repositories/{indexed}/graph/impact",
        json={"node_id": by_path["app/session.py"], "direction": "dependents", "max_depth": 3},
    ).json()
    affected = {item["node"]["file_path"] for item in impact["affected"]}
    assert "app/auth.py" in affected
    assert impact["evidence"]
    assert auth_id  # auth node exists


def test_search_finds_content_and_symbols(indexed, auth_client, fake_github):
    hits = auth_client.get(
        f"/api/v1/repositories/{indexed}/search", params={"q": "refresh_session"}
    ).json()
    assert hits
    assert any(hit["path"] == "app/auth.py" for hit in hits)
    assert all({"path", "line", "match_type", "snippet"} <= set(hit) for hit in hits)


def test_risk_analysis_is_evidenced(indexed, auth_client, fake_github):
    response = auth_client.post(
        f"/api/v1/repositories/{indexed}/risks/analyze",
        json={"include_github_history": True},
    )
    assert response.status_code == 202
    job_service.execute_job(response.json()["job_id"])

    summary = auth_client.get(f"/api/v1/repositories/{indexed}/risks/summary").json()
    assert summary["analysis_run_id"]
    assert summary["overall_score"] is not None
    assert 0 <= summary["overall_score"] <= 100
    assert "drop" not in summary["signals_available"]
    findings = auth_client.get(f"/api/v1/repositories/{indexed}/risks").json()
    assert findings, "the demo repository should produce at least one finding"
    finding = findings[0]
    assert finding["evidence_json"]["signals"]
    assert finding["evidence_json"]["weights"]
    assert finding["origin"] == "measured"
    assert finding["recommendations_json"]
    detail = auth_client.get(
        f"/api/v1/repositories/{indexed}/risks/{finding['id']}"
    ).json()
    assert detail["signals"]


def test_investigation_runs_all_agents_and_verifies_evidence(indexed, auth_client, fake_github):
    created = auth_client.post(
        f"/api/v1/repositories/{indexed}/investigations",
        json={"question": "Why does the authentication refresh lose the session token?"},
    )
    assert created.status_code == 202, created.text
    investigation_id = created.json()["id"]
    job_service.execute_job(created.json()["job_id"])

    detail = auth_client.get(f"/api/v1/investigations/{investigation_id}").json()
    assert detail["status"] == "completed", detail
    assert detail["progress"] == 100
    assert detail["summary"]
    assert detail["result"]["hypotheses"], "evidence exists for this question"
    for hypothesis in detail["result"]["hypotheses"]:
        assert hypothesis["evidence"]
        for evidence in hypothesis["evidence"]:
            assert evidence["file"]
            assert evidence["origin"] in {"measured", "inferred", "ai_suggested"}
    agent_statuses = {run["agent_name"]: run["status"] for run in detail["agent_runs"]}
    assert set(agent_statuses) == {
        "repository_mapper",
        "bug_investigator",
        "risk_analyst",
        "architecture_reviewer",
        "review_planner",
    }
    assert all(status == "completed" for status in agent_statuses.values())
    assert detail["result"]["plan"]
    assert detail["ai_used"] is False


def test_report_generation_and_markdown_export(indexed, auth_client, fake_github):
    response = auth_client.post(
        f"/api/v1/repositories/{indexed}/reports", json={"title": "Release review"}
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert "Release review" in report["markdown"]
    assert "a" * 40 in report["markdown"]
    assert "## Risk summary" in report["markdown"]
    assert "not a probability" in report["markdown"]
    export = auth_client.get(f"/api/v1/reports/{report['id']}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/markdown")
    assert "attachment" in export.headers["content-disposition"]


def test_activity_reports_real_and_unavailable_sections(indexed, auth_client, fake_github):
    activity = auth_client.get(f"/api/v1/repositories/{indexed}/activity").json()
    assert activity["commits"]["available"] is True
    assert activity["commits"]["items"][0]["message"] == "Refactor authentication refresh"
    assert activity["pull_requests"]["items"][0]["number"] == 7
    assert activity["workflows"]["available"] is False
    assert activity["workflows"]["reason"]


def test_duplicate_import_is_idempotent(indexed, auth_client):
    again = auth_client.post(
        "/api/v1/repositories", json={"url": "https://github.com/acme/demo"}
    )
    assert again.status_code == 200
    assert again.json()["id"] == indexed
    listed = auth_client.get("/api/v1/repositories").json()
    assert listed["total"] == 1


def test_dashboard_uses_stored_records(indexed, auth_client):
    stats = auth_client.get("/api/v1/dashboard").json()
    assert stats["repository_count"] == 1
    assert stats["indexed_file_count"] >= 6
    assert stats["repositories"][0]["full_name"] == "acme/demo"
    assert "low" in stats["risk_distribution"]


def test_cross_user_access_is_denied(indexed, client, app):

    other = TestClient(app)
    register(other, email="other@example.com")
    other.headers.update({"X-CSRF-Token": other.cookies.get("nexus_csrf") or ""})
    assert other.get(f"/api/v1/repositories/{indexed}").status_code == 404
    assert other.get(f"/api/v1/repositories/{indexed}/overview").status_code == 404
    assert other.get(f"/api/v1/repositories/{indexed}/graph").status_code == 404


def test_investigation_requires_an_indexed_repository(auth_client, fake_github):
    response = auth_client.post("/api/v1/repositories", json={"url": "https://github.com/acme/demo"})
    repository_id = response.json()["id"]
    created = auth_client.post(
        f"/api/v1/repositories/{repository_id}/investigations",
        json={"question": "Why is this not indexed yet?"},
    )
    assert created.status_code == 409
    assert created.json()["error"]["code"] == "conflict"


def test_jobs_are_scoped_to_the_owner(indexed, auth_client, app):

    job = auth_client.post(f"/api/v1/repositories/{indexed}/index")
    assert job.status_code == 202
    job_id = job.json()["id"]
    assert auth_client.get(f"/api/v1/jobs/{job_id}").status_code == 200

    other = TestClient(app)
    register(other, email="jobs@example.com")
    assert other.get(f"/api/v1/jobs/{job_id}").status_code == 404
