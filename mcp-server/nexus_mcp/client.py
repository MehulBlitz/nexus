"""Authenticated HTTP client for the NEXUS API.

The MCP server never touches the database and never re-implements analysis. It calls the same
versioned API the web application uses, with a personal API token, so repository ownership and
authorisation are enforced once, in the backend.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class NexusApiError(RuntimeError):
    """A readable failure from the NEXUS API.

    The token is never included in messages, URLs, or repr output.
    """

    def __init__(self, message: str, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class NexusClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("NEXUS_API_URL must be an absolute http(s) URL")
        if not token or token.strip() != token:
            raise ValueError("NEXUS_API_TOKEN is missing or malformed")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._transport = transport

    def __repr__(self) -> str:
        return f"NexusClient(base_url={self.base_url!r}, token=***)"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if not path.startswith("/"):
            raise ValueError("API path must start with /")
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self._timeout,
                transport=self._transport,
                headers=headers,
            ) as client:
                response = client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise NexusApiError("NEXUS API timed out") from exc
        except httpx.HTTPError as exc:
            raise NexusApiError("NEXUS API is unreachable") from exc

        if response.status_code >= 400:
            message = f"NEXUS API returned HTTP {response.status_code}"
            code = None
            try:
                body = response.json()
                detail = (body or {}).get("error") or {}
                message = detail.get("message") or message
                code = detail.get("code")
            except ValueError:
                pass
            raise NexusApiError(message, response.status_code, code)
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise NexusApiError("NEXUS API returned a non-JSON response") from exc

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, json=json)
