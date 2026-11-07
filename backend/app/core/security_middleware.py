"""Security middleware: origin checks, rate limiting and hardening headers."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.errors import error_body
from app.core.rate_limit import SlidingWindowLimiter

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
AUTH_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/change-password",
    "/api/v1/auth/account",
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        settings: Settings,
        api_limiter: SlidingWindowLimiter,
        auth_limiter: SlidingWindowLimiter,
    ) -> None:
        super().__init__(app)
        self.settings = settings
        self.api_limiter = api_limiter
        self.auth_limiter = auth_limiter
        self.allowed_origins = {o.rstrip("/") for o in settings.cors_origin_list}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith("/api/v1"):
            if request.method in UNSAFE_METHODS:
                origin = request.headers.get("origin")
                # A browser sends Origin on cross-site writes. Refuse anything not allow-listed.
                if origin and origin.rstrip("/") not in self.allowed_origins:
                    return JSONResponse(
                        error_body("forbidden", "Origin is not allowed"), status_code=403
                    )
            if self.settings.rate_limit_enabled:
                key = self._client_key(request)
                is_auth = any(path.startswith(p) for p in AUTH_PATHS)
                limiter = self.auth_limiter if is_auth else self.api_limiter
                allowed, _remaining, retry_after = limiter.check(f"{key}:{is_auth}")
                if not allowed:
                    response = JSONResponse(
                        error_body("rate_limited", "Too many requests. Try again shortly."),
                        status_code=429,
                    )
                    response.headers["Retry-After"] = str(max(1, int(retry_after)))
                    return response
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @staticmethod
    def _client_key(request: Request) -> str:
        # Only the socket peer address is trusted; X-Forwarded-For is client-controlled unless
        # a trusted proxy is configured, so it is deliberately ignored.
        return request.client.host if request.client else "unknown"
