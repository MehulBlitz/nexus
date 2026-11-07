"""Authentication endpoints: register, login, logout, refresh, me, tokens, account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_auth_context, get_db, require_csrf, require_user
from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.schemas.auth import (
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenOut,
    AuthResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from app.services import auth_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response, settings: Settings, *, token: str, csrf: str, max_age: int
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    # Readable by the SPA so it can echo it in X-CSRF-Token (double submit).
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def _auth_response(issued: auth_service.IssuedSession) -> AuthResponse:
    return AuthResponse(
        user=UserOut.model_validate(issued.user),
        csrf_token=issued.csrf_token,
        expires_at=issued.expires_at,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    issued = auth_service.register(
        db,
        email=str(body.email),
        password=body.password,
        display_name=body.display_name,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    max_age = settings.session_ttl_hours * 3600
    _set_auth_cookies(
        response, settings, token=issued.token, csrf=issued.csrf_token, max_age=max_age
    )
    return _auth_response(issued)


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    issued = auth_service.login(
        db,
        email=str(body.email),
        password=body.password,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    max_age = settings.session_ttl_hours * 3600
    _set_auth_cookies(
        response, settings, token=issued.token, csrf=issued.csrf_token, max_age=max_age
    )
    return _auth_response(issued)


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    context: AuthContext | None = Depends(get_auth_context),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    if context is None or context.session_record is None:
        raise UnauthorizedError("No active session to refresh")
    issued = auth_service.rotate_session(
        db, context.session_record, user_agent=request.headers.get("user-agent")
    )
    db.commit()
    max_age = settings.session_ttl_hours * 3600
    _set_auth_cookies(
        response, settings, token=issued.token, csrf=issued.csrf_token, max_age=max_age
    )
    return _auth_response(issued)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    context: AuthContext | None = Depends(get_auth_context),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    auth_service.logout(db, context.session_record if context else None)
    db.commit()
    _clear_auth_cookies(response, settings)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(context: AuthContext = Depends(require_user)) -> UserOut:
    return UserOut.model_validate(context.user)


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    auth_service.change_password(
        db, context, current_password=body.current_password, new_password=body.new_password
    )
    db.commit()
    _clear_auth_cookies(response, settings)
    response.status_code = 204
    return response


@router.post("/account", status_code=204)
def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    auth_service.delete_account(db, context, password=body.password)
    db.commit()
    _clear_auth_cookies(response, settings)
    response.status_code = 204
    return response


@router.get("/tokens", response_model=list[ApiTokenOut])
def list_tokens(
    context: AuthContext = Depends(require_user), db: Session = Depends(get_db)
) -> list[ApiTokenOut]:
    records = auth_service.list_api_tokens(db, context.user.id)
    return [ApiTokenOut.model_validate(r) for r in records]


@router.post("/tokens", response_model=ApiTokenCreated, status_code=201)
def create_token(
    body: ApiTokenCreate,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ApiTokenCreated:
    token, record = auth_service.create_api_token(
        db, user_id=context.user.id, name=body.name
    )
    db.commit()
    return ApiTokenCreated(token=token, record=ApiTokenOut.model_validate(record))


@router.delete("/tokens/{token_id}", status_code=204)
def revoke_token(
    token_id: str,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Response:
    auth_service.revoke_api_token(db, user_id=context.user.id, token_id=token_id)
    db.commit()
    return Response(status_code=204)
