"""
Bot users: integration identities weaker than the user that owns them, their
token, and the caller schemas `GET /caller` answers with (FR-08, spec #245).
"""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints, model_validator
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from .shared import get_datetime_utc
from .webhook import BotWebhooks

BotUserName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class BotUserRef(SQLModel):
    """
    A bot user as a task or comment names it: the one it is assigned to, or
    the one that wrote it. A deleted bot user stays on what it was given and
    what it wrote (FR-08.19, FR-08.21), marked deleted.
    """

    id: uuid.UUID
    name: str
    deleted: bool


class BotPermissions(SQLModel):
    """
    What a bot user may do inside the projects of its scope (FR-08.9,
    FR-08.10).

    Only what can be granted is here. What a bot can never do — anything on
    projects, editing or deleting comments, renaming or deleting tags — has no
    field to set to false: the endpoints for it take a human caller, so a bot
    cannot reach them at all. Reading tags needs no field either: every bot
    user reads its owner's whole tag vocabulary, whatever its scope
    (ADR-0003).
    """

    create_tasks: bool = False
    read_tasks: bool = False
    update_tasks: bool = False
    delete_tasks: bool = False
    add_comments: bool = False
    # Covers both creating a tag on its own and typing a name that is not a
    # tag yet onto a task (FR-08.9).
    create_tags: bool = False
    # Reading the activity log does not follow from `read_tasks`: the log
    # shows the owner's own work too, so it is its own grant (spec #246,
    # FR-08.9). This slice only makes the grant exist and persist; serving
    # the log to a bot user is #251.
    read_activity: bool = False


class BotScope(SQLModel):
    """
    Where a bot user may act and what it may do there.

    The projects are always named one by one: there is no value meaning "all
    projects" (FR-08.6), so a project created tomorrow is never in the scope
    of a bot set up today.
    """

    project_ids: list[uuid.UUID]
    permissions: BotPermissions


class ActorKind(StrEnum):
    """The two kinds of caller `GET /caller` ever describes (spec #245)."""

    USER = "user"
    BOT_USER = "bot_user"


class CallerActor(SQLModel):
    """
    Who is making a request to `GET /caller`: a human user by their own id
    and name, or a bot user by its own id and the name its owner gave it.
    """

    kind: ActorKind
    id: uuid.UUID
    name: str


class CallerProject(SQLModel):
    """
    One project in a bot user's scope, as `GET /caller` reports it: just
    enough to file work into the right place without guessing (stories 6-8 of
    spec #245). An archived project never appears here, whatever the scope
    says (FR-05.13).
    """

    id: uuid.UUID
    name: str
    is_inbox: bool
    open_tasks: int


class CallerPublic(SQLModel):
    """
    What `GET /caller` answers for whoever calls it, human or bot user: who is
    calling, whose data the call reaches, what it may do there, and today's
    date on this installation (spec #245). Read-only, so nothing here is ever
    logged (FR-10.1).
    """

    actor: CallerActor
    # Whose data this request reaches: the caller's own id for a human, the
    # owning user's for a bot user — never anyone else's (FR-08.2).
    owner_id: uuid.UUID
    # One boolean per grant a scope can hold. Every one is true for a human,
    # who may do anything a scope could grant; exactly the bot user's own
    # grants otherwise (FR-08.9).
    permissions: BotPermissions
    # The full scope for a bot user, Inbox first then by name ignoring case,
    # the same order the project list uses; `None` for a human, who reads
    # their projects from the project list instead (FR-08.6).
    projects: list[CallerProject] | None = None
    today: date


class BotUserCreate(SQLModel):
    name: BotUserName
    scope: BotScope


class BotUserUpdate(SQLModel):
    """
    A change to a bot user: its name, its scope, or both. A scope is sent
    whole — its projects and its permissions — and replaces the one the bot
    user had, so what is granted is always exactly what the user last saw.
    """

    name: BotUserName | None = None
    scope: BotScope | None = None


class BotUser(SQLModel, table=True):
    """
    An identity for an integration, owned by one user and far weaker than
    them (FR-08.1–FR-08.4).

    Not a kind of `User`: sign-in, registration, recovery and the
    superuser's account list all work on users, so none of them can reach a
    bot user by forgetting to check for one. It has no password and no email;
    the only way in is its token.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    name: str = Field(max_length=255)
    create_tasks: bool = False
    read_tasks: bool = False
    update_tasks: bool = False
    delete_tasks: bool = False
    add_comments: bool = False
    create_tags: bool = False
    # Off by default (spec #246, FR-08.9): reading the log is its own grant,
    # not implied by `read_tasks`. See `BotPermissions.read_activity`.
    read_activity: bool = False
    # A SHA-256 of the token, never the token itself, so the token cannot be
    # read back from anywhere once the response that issued it is gone
    # (FR-08.13). One column, so a bot user holds at most one token
    # (FR-08.12). A token is random and long, which is what makes a plain
    # digest enough where a password needs a slow hash.
    token_hash: str | None = Field(
        default=None, max_length=64, unique=True, nullable=True
    )
    token_issued_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # Optional; past it the token is refused like any other invalid one
    # (FR-08.14).
    token_expires_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # Approximate, not exact: see `deps.record_bot_token_use` (FR-08.17).
    token_last_used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # When the last token was revoked. Revoking clears `token_hash`, so this
    # is all that is left of it: enough to tell the user why the bot user has
    # no token (FR-08.15).
    token_revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # The bot user's two webhooks (FR-11.1), each optional. Only the owner sets
    # them, through the bot users' endpoints a bot user cannot call (FR-11.2).
    task_webhook_url: str | None = Field(default=None, max_length=2048)
    comment_webhook_url: str | None = Field(default=None, max_length=2048)
    # The one secret both webhooks are signed with (FR-11.9), kept encrypted.
    # A digest could not do: signing needs the secret itself, and it is shown
    # to the owner only once. Encrypted under `WEBHOOK_SECRET_KEY`; see
    # `app.webhooks.encrypt_secret`.
    webhook_secret_encrypted: str | None = Field(default=None, max_length=512)
    # Set once the bot user is deleted. It is kept rather than removed, so
    # what it did and what it was assigned still name it (FR-08.19, FR-08.21).
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class BotUserProject(SQLModel, table=True):
    """The projects in a bot user's scope, each listed explicitly."""

    bot_user_id: uuid.UUID = Field(
        foreign_key="botuser.id", primary_key=True, ondelete="CASCADE"
    )
    project_id: uuid.UUID = Field(
        foreign_key="project.id", primary_key=True, ondelete="CASCADE"
    )


class BotUserPublic(SQLModel):
    id: uuid.UUID
    name: str
    scope: BotScope
    # A deleted bot user is kept, so its record still opens and still says
    # what it now is (FR-08.19). It is gone from the list either way.
    deleted: bool = False
    # When it was deleted, for the section that keeps deleted bot users in view.
    deleted_at: datetime | None = None
    # The tasks that still name it as their assignee, deleted ones left out:
    # what a deleted bot user is still on the record for (FR-08.21).
    assigned_task_count: int = 0
    # Whether a token is out, revoked or not; the token itself is never
    # reported again. One that has expired is still out until it is revoked.
    has_token: bool
    token_issued_at: datetime | None = None
    token_expires_at: datetime | None = None
    token_last_used_at: datetime | None = None
    token_revoked_at: datetime | None = None
    # Only the owner reads a bot user through this shape, and a bot user never
    # does (FR-11.2).
    webhooks: BotWebhooks
    created_at: datetime | None = None


class BotUsersPublic(SQLModel):
    data: list[BotUserPublic]
    count: int


class WebhookSet(SQLModel):
    """
    The result of setting a webhook. `secret` is set only when this call
    generated it (the bot user's first webhook): it is shown once (FR-11.9).
    """

    bot_user: BotUserPublic
    secret: str | None = None


class WebhookSecretIssued(SQLModel):
    """The one response that carries a regenerated secret (FR-11.9)."""

    bot_user_id: uuid.UUID
    secret: str


class BotTokenIssue(SQLModel):
    """How a token is issued: with an expiry, or none to last until revoked."""

    expires_at: datetime | None = None

    @model_validator(mode="after")
    def check_expiry(self) -> BotTokenIssue:
        if self.expires_at is None:
            return self
        if self.expires_at.tzinfo is None:
            raise ValueError("`expires_at` needs a timezone")
        if self.expires_at <= datetime.now(UTC):
            raise ValueError("`expires_at` has to be in the future")
        return self


class BotTokenIssued(SQLModel):
    """The one response that carries a bot user's token (FR-08.13)."""

    bot_user_id: uuid.UUID
    token: str
    expires_at: datetime | None = None
