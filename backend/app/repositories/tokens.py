"""Database access for browser sessions and personal API tokens."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import ensure_utc, utcnow
from app.models.user import ApiToken, UserSession


def create_session(
    session: Session, *, user_id: str, token_hash: str, expires_at: datetime, user_agent: str | None
) -> UserSession:
    record = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=(user_agent or "")[:200] or None,
    )
    session.add(record)
    session.flush()
    return record


def get_session_by_hash(session: Session, token_hash: str) -> UserSession | None:
    return session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))


def get_active_session(session: Session, token_hash: str) -> UserSession | None:
    record = get_session_by_hash(session, token_hash)
    if record is None or record.revoked_at is not None:
        return None
    if ensure_utc(record.expires_at) <= utcnow():
        return None
    return record


def revoke_session(session: Session, record: UserSession) -> None:
    record.revoked_at = utcnow()
    session.flush()


def revoke_all_sessions(session: Session, user_id: str, *, except_id: str | None = None) -> int:
    records = list(
        session.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
            )
        )
    )
    now = utcnow()
    count = 0
    for record in records:
        if except_id and record.id == except_id:
            continue
        record.revoked_at = now
        count += 1
    session.flush()
    return count


def create_api_token(
    session: Session, *, user_id: str, name: str, token_hash: str, prefix: str, scope: str
) -> ApiToken:
    record = ApiToken(
        user_id=user_id, name=name, token_hash=token_hash, prefix=prefix, scope=scope
    )
    session.add(record)
    session.flush()
    return record


def get_active_api_token(session: Session, token_hash: str) -> ApiToken | None:
    record = session.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash))
    if record is None or record.revoked_at is not None:
        return None
    return record


def list_api_tokens(session: Session, user_id: str) -> list[ApiToken]:
    return list(
        session.scalars(
            select(ApiToken)
            .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
            .order_by(ApiToken.created_at.desc())
        )
    )


def get_api_token(session: Session, user_id: str, token_id: str) -> ApiToken | None:
    record = session.get(ApiToken, token_id)
    if record is None or record.user_id != user_id:
        return None
    return record


def touch_api_token(session: Session, record: ApiToken) -> None:
    record.last_used_at = utcnow()
