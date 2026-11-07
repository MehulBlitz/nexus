import json
import logging

from hypothesis import given
from hypothesis import strategies as st

from app.core.logging import JsonFormatter, redact


def test_redacts_key_value_secrets():
    out = redact("login password=hunter2 ok")
    assert "hunter2" not in out and "[REDACTED]" in out


def test_redacts_bearer_and_github_tokens():
    assert "abcdefgh12345678" not in redact("Authorization: Bearer abcdefgh12345678")
    assert "ghp_" not in redact("token ghp_" + "a" * 36)


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=6, max_size=30))
def test_property_password_values_never_survive(value):
    assert value not in redact(f"password={value}")


def test_formatter_emits_json_with_request_id():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("w",), None)
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "hello w"
    assert data["level"] == "INFO"
    assert "request_id" in data and "timestamp" in data
