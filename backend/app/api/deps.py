"""FastAPI dependencies: database session, authentication, CSRF and ownership."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import tokens_equal
from app.models.repository import Repository
from app.models.user import User
from app.services import auth_service
from app.services.auth_service import AuthContext


def get_db() -> Iterator[Session]:
    yield from get_session()


def get_auth_context(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> AuthContext | None:
    header = request.headers.get("Authorization", "")
    bearer = header[7:].strip() if header.lower().startswith("bearer ") else None
    cookie = request.cookies.get(settings.session_cookie_name)
    return auth_service.resolve_auth(db, session_token=cookie, bearer_token=bearer)


def require_user(context: AuthContext | None = Depends(get_auth_context)) -> AuthContext:
    if context is None:
        raise UnauthorizedError("Authentication required")
    return context


def require_csrf(
    request: Request,
    context: AuthContext = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """Double-submit CSRF check for cookie-authenticated mutating requests.

    Bearer-token callers are not vulnerable to CSRF and are exempt.
    """
    if context.method == "session" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        cookie = request.cookies.get(settings.csrf_cookie_name, "")
        header = request.headers.get("X-CSRF-Token", "")
        if not cookie or not header or not tokens_equal(cookie, header):
            raise ForbiddenError("Missing or invalid CSRF token")
    return context


def current_user(context: AuthContext = Depends(require_user)) -> User:
    return context.user


def owned_repository(
    repository_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Repository:
    return auth_service.owned_repository(db, user.id, repository_id)
