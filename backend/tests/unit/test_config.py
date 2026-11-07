import pytest
from pydantic import ValidationError

from app.core.config import Settings

GOOD_SECRET = "x" * 40
PROD = {
    "app_env": "production",
    "app_secret_key": GOOD_SECRET,
    "database_url": "postgresql+psycopg://u:p@db:5432/n",
    "cors_origins": "https://nexus.example.com",
}


def test_defaults_are_development():
    s = Settings(_env_file=None)
    assert s.app_env in {"development", "test"}


def test_valid_production_settings_accepted():
    assert Settings(_env_file=None, **PROD).app_env == "production"


@pytest.mark.parametrize("secret", ["replace-me", "change-me", "", "short"])
def test_production_rejects_weak_secret(secret):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**PROD, "app_secret_key": secret})


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**PROD, "cors_origins": "*"})


def test_production_rejects_sqlite():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**PROD, "database_url": "sqlite:///x.db"})


def test_invalid_log_level_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="LOUD")


def test_cors_list_parsing():
    s = Settings(_env_file=None, cors_origins="http://a.com, http://b.com ,")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]
