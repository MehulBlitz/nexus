import os

os.environ.setdefault("APP_ENV", "test")
# A file database (not :memory:) so parallel agent threads use independent connections.
os.environ.setdefault("DATABASE_URL", "sqlite:///./nexus_test.sqlite3")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("JOB_EXECUTION_MODE", "worker")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401 - registers every table on Base.metadata
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, get_engine, get_sessionmaker  # noqa: E402

VALID_PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _clear_caches():
    for fn in (get_settings, get_engine, get_sessionmaker):
        fn.cache_clear()
    yield
    for fn in (get_settings, get_engine, get_sessionmaker):
        fn.cache_clear()


@pytest.fixture
def app():
    from app.main import create_app

    application = create_app()
    Base.metadata.create_all(get_engine())
    yield application
    Base.metadata.drop_all(get_engine())


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def db_session():
    Base.metadata.create_all(get_engine())
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(get_engine())


def register(client: TestClient, email: str = "dev@example.com", password: str = VALID_PASSWORD):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Dev User"},
    )


@pytest.fixture
def auth_client(client):
    response = register(client)
    assert response.status_code == 201, response.text
    csrf = client.cookies.get("nexus_csrf")
    client.headers.update({"X-CSRF-Token": csrf or ""})
    return client
