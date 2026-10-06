import warnings
from typing import Literal, Self

from pydantic import (
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    # The installation's public address. Passkeys are bound to its hostname
    # (FR-12.4): changing it makes every passkey issued so far unusable.
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn
    # Database used by backend/scripts/test.sh, on the same server as DATABASE_URL
    TEST_DB_NAME: str = "app_test"

    # Where the default local attachment storage backend keeps files (ADR-0002).
    ATTACHMENTS_DIR: str = "data/attachments"
    # Read by the upload endpoint rather than hard-coded, so the limit can be
    # tuned per deployment without a code change (FR-04.2).
    ATTACHMENT_MAX_SIZE_BYTES: int = 25 * 1024 * 1024

    # Whether a webhook URL (or a Paperless address) may point at loopback or a
    # private range (FR-11.3, FR-04.4). Off by default, because anyone can
    # register and would otherwise be able to probe the server's own network.
    # Turn it on for an installation whose agents run on the same machine or
    # LAN, which is the case the default forbids (ADR-0009).
    OUTBOUND_ALLOW_PRIVATE_ADDRESSES: bool = False

    # Whether this API process drains the webhook outbox in the background
    # (ADR-0009). Every process may; they never send the same delivery twice.
    WEBHOOK_DELIVERY_LOOP: bool = True
    # How often the loop looks for due deliveries, in seconds. A delivery made
    # by this process is picked up at once, whatever this says.
    WEBHOOK_POLL_SECONDS: float = 5.0

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    # Whoever registers this address while the installation has no superuser
    # becomes it (FR-09.6).
    FIRST_SUPERUSER: EmailStr

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])

        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
