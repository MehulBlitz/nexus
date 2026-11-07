"""Authentication, session issuance, API tokens and account lifecycle."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import utcnow
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableError,
)
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    needs_rehash,
    password_problem,
    token_prefix,
    verify_password,
)
from app.models.user import AccountDeletionRequest, ApiToken, User, UserSession
from app.repositories import jobs as jobs_repo
from app.repositories import repos as repos_repo
from app.repositories import tokens as tokens_repo
from app.repositories import users as users_repo


@dataclass(frozen=True)
class AuthContext:
    user: User
    method: str  # "session" | "token"
    session_record: UserSession | None = None
    api_token: ApiToken | None = None


@dataclass(frozen=True)
class IssuedSession:
    user: User
    token: str
    csrf_token: str
    expires_at: datetime


def _default_scope() -> str:
    return "read"


def register(
    session: Session, *, email: str, password: str, display_name: str, user_agent: str | None
) -> IssuedSession:
    problem = password_problem(password)
    if problem:
        raise UnprocessableError(problem)
    if users_repo.get_user_by_email(session, email) is not None:
        raise ConflictError("An account with this email already exists")
    user = users_repo.create_user(
        session, email=email, password_hash=hash_password(password), display_name=display_name
    )
    jobs_repo.audit(
        session, user_id=user.id, action="auth.register", resource_type="user", resource_id=user.id
    )
    return _issue_session(session, user, user_agent)


def login(
    session: Session, *, email: str, password: str, user_agent: str | None
) -> IssuedSession:
    user = users_repo.get_user_by_email(session, email)
    # Verify against a dummy hash when the user is unknown so timing does not reveal accounts.
    if user is None:
        hash_password("timing-equaliser-not-a-real-password")
        jobs_repo.audit(
            session, user_id=None, action="auth.login_failed", resource_type="user",
            metadata={"reason": "unknown_user"},
        )
        raise UnauthorizedError("Invalid email or password")
    if not verify_password(password, user.password_hash):
        jobs_repo.audit(
            session, user_id=user.id, action="auth.login_failed", resource_type="user",
            resource_id=user.id, metadata={"reason": "bad_password"},
        )
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise ForbiddenError("This account is disabled")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    jobs_repo.audit(
        session, user_id=user.id, action="auth.login", resource_type="user", resource_id=user.id
    )
    return _issue_session(session, user, user_agent)


def _issue_session(session: Session, user: User, user_agent: str | None) -> IssuedSession:
    settings = _settings()
    token = generate_token()
    csrf = generate_token()
    expires_at = utcnow() + timedelta(hours=settings.session_ttl_hours)
    tokens_repo.create_session(
        session,
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=expires_at,
        user_agent=user_agent,
    )
    return IssuedSession(user=user, token=token, csrf_token=csrf, expires_at=expires_at)


def _settings() -> Settings:
    from app.core.config import get_settings

    return get_settings()


def rotate_session(
    session: Session, record: UserSession, *, user_agent: str | None
) -> IssuedSession:
    """Issue a new token for the same user and revoke the presented one."""
    user = users_repo.get_user(session, record.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Session is no longer valid")
    tokens_repo.revoke_session(session, record)
    return _issue_session(session, user, user_agent)


def logout(session: Session, record: UserSession | None) -> None:
    if record is not None:
        tokens_repo.revoke_session(session, record)
        jobs_repo.audit(
            session, user_id=record.user_id, action="auth.logout", resource_type="session",
            resource_id=record.id,
        )


def resolve_auth(
    session: Session, *, session_token: str | None, bearer_token: str | None
) -> AuthContext | None:
    """Resolve a caller from an Authorization bearer token or the session cookie."""
    if bearer_token:
        token = tokens_repo.get_active_api_token(session, hash_token(bearer_token))
        if token is None:
            return None
        user = users_repo.get_user(session, token.user_id)
        if user is None or not user.is_active:
            return None
        tokens_repo.touch_api_token(session, token)
        return AuthContext(user=user, method="token", api_token=token)
    if session_token:
        record = tokens_repo.get_active_session(session, hash_token(session_token))
        if record is None:
            return None
        user = users_repo.get_user(session, record.user_id)
        if user is None or not user.is_active:
            return None
        return AuthContext(user=user, method="session", session_record=record)
    return None


def change_password(
    session: Session, context: AuthContext, *, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, context.user.password_hash):
        raise UnauthorizedError("Current password is incorrect")
    problem = password_problem(new_password)
    if problem:
        raise UnprocessableError(problem)
    if new_password == current_password:
        raise UnprocessableError("New password must differ from the current password")
    context.user.password_hash = hash_password(new_password)
    revoked = tokens_repo.revoke_all_sessions(session, context.user.id)
    jobs_repo.audit(
        session,
        user_id=context.user.id,
        action="auth.password_changed",
        resource_type="user",
        resource_id=context.user.id,
        metadata={"sessions_revoked": revoked},
    )


def delete_account(session: Session, context: AuthContext, *, password: str) -> None:
    if not verify_password(password, context.user.password_hash):
        raise UnauthorizedError("Password is incorrect")
    user = context.user
    email_hash = hashlib.sha256(user.email.encode("utf-8")).hexdigest()
    jobs_repo.audit(
        session,
        user_id=user.id,
        action="account.deleted",
        resource_type="user",
        resource_id=user.id,
    )
    session.add(AccountDeletionRequest(deleted_user_email_hash=email_hash, note="self-service"))
    session.flush()
    # Deleting the user cascades to repositories, snapshots, investigations, reports and tokens.
    users_repo.delete_user(session, user)


def create_api_token(
    session: Session, *, user_id: str, name: str
) -> tuple[str, ApiToken]:
    token = generate_token()
    record = tokens_repo.create_api_token(
        session,
        user_id=user_id,
        name=name.strip(),
        token_hash=hash_token(token),
        prefix=token_prefix(token),
        scope=_default_scope(),
    )
    jobs_repo.audit(
        session,
        user_id=user_id,
        action="api_token.created",
        resource_type="api_token",
        resource_id=record.id,
    )
    return token, record


def list_api_tokens(session: Session, user_id: str) -> list[ApiToken]:
    return tokens_repo.list_api_tokens(session, user_id)


def revoke_api_token(session: Session, *, user_id: str, token_id: str) -> None:
    record = tokens_repo.get_api_token(session, user_id, token_id)
    if record is None:
        raise NotFoundError("API token not found")
    record.revoked_at = utcnow()
    jobs_repo.audit(
        session, user_id=user_id, action="api_token.revoked", resource_type="api_token",
        resource_id=token_id,
    )


def owned_repository(session: Session, user_id: str, repository_id: str):
    record = repos_repo.get_owned(session, user_id, repository_id)
    if record is None:
        # Same response for missing and not-owned so ids cannot be probed.
        raise NotFoundError("Repository not found")
    return record
