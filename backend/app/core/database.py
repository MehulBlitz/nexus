"""SQLAlchemy engine, declarative base and database health check."""

from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


def utcnow() -> datetime:
    """Timezone-aware current time in UTC. Use for every stored timestamp."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all ORM models (added in later phases)."""


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session():
    """FastAPI dependency yielding a session that is always closed."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def check_database(engine: Engine | None = None) -> tuple[bool, str | None]:
    """Run SELECT 1. Returns (ok, error_class_name). Never leaks connection details."""
    try:
        with (engine or get_engine()).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - any failure means not ready
        return False, type(exc).__name__
