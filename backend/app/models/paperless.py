"""
Paperless: a user's own Paperless-ngx connection, and the hand-over of an
attachment to it (ADR-0010, FR-04).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index
from sqlmodel import Field, SQLModel

from .shared import get_datetime_utc
from .webhook import DeliveryState


class PaperlessConnection(SQLModel, table=True):
    """
    A user's own Paperless-ngx instance (FR-04.4, ADR-0010): one per user, off
    until set. The token is encrypted under `PAPERLESS_TOKEN_KEY` because
    Taskly has to send it back to Paperless; it is never returned by the API.
    """

    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    url: str = Field(max_length=2048)
    token_encrypted: str = Field(max_length=1024)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class PaperlessHandoverStage(StrEnum):
    """What a hand-over does next."""

    # Look for the document by checksum, and send the file if Paperless does
    # not hold it.
    SEND = "send"
    # Wait for Paperless to consume the file it was sent.
    POLL = "poll"
    # The document is known: tag it, note the task, release the local copy.
    FINISH = "finish"


class PaperlessHandover(SQLModel, table=True):
    """
    The outbox row of a PDF being handed to Paperless: the sibling of
    `webhookdelivery`, drained by the same loop on the same retry schedule
    (FR-04.6, FR-11.10). It exists only while the hand-over is unfinished or
    failed; a finished one is deleted, and the attachment carries the result.
    All of its state is here, so a restart loses nothing.
    """

    __table_args__ = (
        Index("ix_paperlesshandover_state_next_attempt_at", "state", "next_attempt_at"),
        CheckConstraint(
            "state IN ('pending', 'failed')", name="paperlesshandover_state"
        ),
        CheckConstraint(
            "stage IN ('send', 'poll', 'finish')", name="paperlesshandover_stage"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    attachment_id: uuid.UUID = Field(
        foreign_key="attachment.id", nullable=False, ondelete="CASCADE", unique=True
    )
    state: str = Field(default=DeliveryState.PENDING.value, max_length=20)
    stage: str = Field(default=PaperlessHandoverStage.SEND.value, max_length=20)
    # Paperless's id for the consumption of the file we sent, and the document
    # it made (or the one that was already there).
    paperless_task_id: str | None = Field(default=None, max_length=100)
    paperless_document_id: int | None = Field(
        default=None,
        sa_type=BigInteger,
    )
    # When the file was sent: how long Paperless has had to consume it.
    sent_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # Failed attempts so far; the retry schedule is read off it.
    attempts: int = 0
    next_attempt_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_attempt_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_error: str | None = Field(default=None, max_length=500)


class PaperlessHandoverPublic(SQLModel):
    """
    A PDF on its way to Paperless: still kept in Taskly, and downloadable from
    there (FR-04.6). `failed` means every attempt was used; `error` says why
    and the owner can send it again.
    """

    state: str
    error: str | None = None
    attempts: int
    # When the next attempt is due, while there is one.
    next_attempt_at: datetime | None = None


class PaperlessConnect(SQLModel):
    """What the owner types: the instance's address and an API token. On a
    change the token may be left out, which keeps the one stored."""

    url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2048)]
    token: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=512)
    ] = None


class PaperlessConnectionPublic(SQLModel):
    """The connection as Settings shows it. There is no token: it is never
    shown again, only replaced (FR-04.4)."""

    connected: bool
    url: str | None = None
    # How many attachments are kept in Paperless, so Settings can say what
    # disconnecting makes unreachable (FR-04.8).
    documents_kept: int = 0


class PaperlessTest(SQLModel):
    """Values to try before saving them; whatever is left out is taken from the
    saved connection."""

    url: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2048)
    ] = None
    token: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=512)
    ] = None


class PaperlessTestResult(SQLModel):
    ok: bool
    # Why it did not work, when it did not.
    error: str | None = None


class PaperlessDisconnected(SQLModel):
    connected: bool = False
    # Attachments kept in Paperless, which are out of reach until a connection
    # is set again (FR-04.8). Nothing in Paperless is touched.
    unreachable_documents: int
