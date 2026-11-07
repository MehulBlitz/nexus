"""SQLAlchemy engine, declarative base and database health check."""

from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def utcnow() -> datetime:
    """Timezone-aware current time in UTC. Use for every stored timestamp."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Return a timezone-aware datetime.

    SQLite does not preserve tzinfo, so values read back from it are naive. They were written
    as UTC, so attaching UTC restores the intended meaning before comparison.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            # Every connection must see the same in-memory database.
            kwargs["poolclass"] = StaticPool
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
