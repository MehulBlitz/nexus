import re

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core import database


def test_health_ok_without_database(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("health must not touch the database")

    monkeypatch.setattr(database, "check_database", boom)
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_ok_with_database(client):
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] == "ok"


def test_ready_503_when_database_down(client, monkeypatch):
    from app.api.v1 import system

    monkeypatch.setattr(system, "check_database", lambda: (False, "OperationalError"))
    r = client.get("/api/v1/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "not_ready"
    assert body["checks"]["database"] == "failed: OperationalError"
    assert "sqlite" not in r.text.lower()


def test_check_database_reports_failure_without_details():
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:////nonexistent_dir_xyz/db.sqlite3")
    ok, err = database.check_database(engine)
    assert ok is False and err == "OperationalError"


def test_version(client):
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    assert r.json()["name"] == "NEXUS" and r.json()["environment"] == "test"


def test_response_has_generated_request_id(client):
    rid = client.get("/api/v1/health").headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", rid)


def test_valid_supplied_request_id_is_echoed(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert r.headers["X-Request-ID"] == "trace-abc-12345"


@settings(max_examples=40, deadline=None)
@given(st.text(min_size=1, max_size=40).filter(lambda s: s.isascii() and s.isprintable()))
def test_property_response_request_id_is_always_safe(value):
    from fastapi.testclient import TestClient

    from app.main import create_app

    r = TestClient(create_app()).get("/api/v1/health", headers={"X-Request-ID": value})
    assert re.fullmatch(r"[A-Za-z0-9._-]{8,64}", r.headers["X-Request-ID"])


def test_unknown_route_uses_standard_error_body(client):
    r = client.get("/api/v1/nope")
    body = r.json()
    assert r.status_code == 404
    assert body["error"]["code"] == "http_404"
    assert body["error"]["request_id"] == r.headers["X-Request-ID"]


def test_unhandled_exception_hides_internals(client):
    from fastapi import FastAPI

    from app.main import create_app

    app: FastAPI = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    from fastapi.testclient import TestClient

    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in r.text
    assert "Traceback" not in r.text


def test_app_error_maps_to_body(client):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.errors import NotFoundError
    from app.main import create_app

    app: FastAPI = create_app()

    @app.get("/missing")
    def missing():
        raise NotFoundError("Repository not found")

    r = TestClient(app).get("/missing")
    assert r.status_code == 404
    assert r.json()["error"] == {
        "code": "not_found",
        "message": "Repository not found",
        "request_id": r.headers["X-Request-ID"],
    }


def test_openapi_served(client):
    assert client.get("/api/v1/openapi.json").status_code == 200
