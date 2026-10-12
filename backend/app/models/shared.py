"""
Shared timestamp factory and small schemas common to several domains: a generic
message, the token pair, and the one deletion event every soft-deleted row points at.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class Deletion(SQLModel, table=True):
    """
    One deletion event: every row that went down with it points here.

    Deleting is soft — nothing leaves the database — so a restore needs to know
    which rows belong to *this* deletion. A subtask deleted on its own earlier
    keeps its own event and is left behind when its parent is restored
    (FR-01.10).
    """

    __table_args__ = (
        # The event names the one thing the user pointed at; everything else
        # went down as a cascade. A batch points at nothing in particular —
        # the user pointed at a selection — so both are empty there, and the
        # rows that carry the event are the whole of what it took down.
        CheckConstraint(
            "NOT (task_id IS NOT NULL AND project_id IS NOT NULL)",
            name="deletion_targets_one_thing",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    task_id: uuid.UUID | None = Field(
        default=None, foreign_key="task.id", nullable=True, ondelete="CASCADE"
    )
    project_id: uuid.UUID | None = Field(
        default=None, foreign_key="project.id", nullable=True, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
    # The user's session version when the token was issued. A token from
    # before the account last signed out everywhere carries a lower one.
    sv: int | None = None
