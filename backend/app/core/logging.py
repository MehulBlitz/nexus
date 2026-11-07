"""Structured JSON logging with correlation IDs and secret redaction."""

import json
import logging
import re
from datetime import UTC, datetime

from app.core.request_context import get_request_id

_SECRET_PATTERNS = [
    # key=value or "key": "value" for sensitive-looking keys
    re.compile(
        r"""(?i)(password|passwd|secret|token|api[_-]?key|authorization)(["']?\s*[:=]\s*["']?)([^\s"',}&]+)"""
    ),
    # Bearer tokens
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]{8,})"),
    # GitHub tokens
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
]


def redact(text: str) -> str:
    """Replace values that look like secrets with a fixed marker.

    Bearer and token patterns run first so that "Authorization: Bearer <tok>" is fully masked
    before the generic key=value rule sees the word "Bearer" as the value.
    """
    text = _SECRET_PATTERNS[1].sub(r"\1[REDACTED]", text)
    text = _SECRET_PATTERNS[2].sub("[REDACTED]", text)
    return _SECRET_PATTERNS[0].sub(r"\1\2[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
