import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_engine, get_sessionmaker  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_caches():
    for fn in (get_settings, get_engine, get_sessionmaker):
        fn.cache_clear()
    yield
    for fn in (get_settings, get_engine, get_sessionmaker):
        fn.cache_clear()


@pytest.fixture
def client():
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)
