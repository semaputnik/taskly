"""How the settings treat the installation's secrets (FR-11.9)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DATABASE_URL = "postgresql://postgres:a-real-password@localhost:5432/app"


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test run itself is a development process: do not let that leak in."""
    monkeypatch.delenv("FASTAPI_ENV", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET_KEY", raising=False)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "PROJECT_NAME": "Taskly",
        "SECRET_KEY": "a-real-secret-key",
        "WEBHOOK_SECRET_KEY": "a-real-webhook-key",
        "FIRST_SUPERUSER": "admin@example.com",
        "DATABASE_URL": DATABASE_URL,
    }
    values.update(overrides)
    # No .env file may change what is under test.
    return Settings(_env_file=None, **values)  # type: ignore[arg-type, call-arg]


def test_a_development_installation_works_without_setting_the_key() -> None:
    values = {
        "PROJECT_NAME": "Taskly",
        "SECRET_KEY": "a-real-secret-key",
        "FIRST_SUPERUSER": "admin@example.com",
        "DATABASE_URL": DATABASE_URL,
        "FASTAPI_ENV": "development",
    }
    with pytest.warns(UserWarning, match="WEBHOOK_SECRET_KEY"):
        settings = Settings(_env_file=None, **values)  # type: ignore[arg-type, call-arg]

    assert settings.WEBHOOK_SECRET_KEY == "changethis"


def test_a_development_installation_only_warns_about_the_default_key() -> None:
    with pytest.warns(UserWarning, match="WEBHOOK_SECRET_KEY"):
        _settings(WEBHOOK_SECRET_KEY="changethis", FASTAPI_ENV="development")


def test_a_deployed_installation_refuses_the_default_webhook_secret_key() -> None:
    with pytest.raises(ValidationError, match="WEBHOOK_SECRET_KEY"):
        _settings(WEBHOOK_SECRET_KEY="changethis")


def test_a_deployed_installation_that_leaves_the_key_unset_is_refused() -> None:
    values = {
        "PROJECT_NAME": "Taskly",
        "SECRET_KEY": "a-real-secret-key",
        "FIRST_SUPERUSER": "admin@example.com",
        "DATABASE_URL": DATABASE_URL,
    }
    with pytest.raises(ValidationError, match="WEBHOOK_SECRET_KEY"):
        Settings(_env_file=None, **values)  # type: ignore[arg-type, call-arg]


def test_a_deployed_installation_accepts_a_real_webhook_secret_key() -> None:
    assert _settings().WEBHOOK_SECRET_KEY == "a-real-webhook-key"
