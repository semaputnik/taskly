"""
Webhooks: the outbox a bot user's two webhooks are delivered through
(ADR-0009, FR-11).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints
from sqlalchemy import CheckConstraint, DateTime, Index
from sqlmodel import Field, SQLModel

from .shared import get_datetime_utc


class WebhookKind(StrEnum):
    """The bot user's two webhooks (FR-11.1)."""

    TASK = "task"
    COMMENT = "comment"


class WebhookEventType(StrEnum):
    """What a delivery says happened (FR-11.8)."""

    TASK_READY = "task.ready"
    COMMENT_ADDED = "comment.added"
    TEST = "test"


class DeliveryState(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class WebhookDelivery(SQLModel, table=True):
    """
    One event on its way to one webhook: the outbox (ADR-0009, FR-11.10).

    Written in the transaction of the change that caused it, so an event never
    lands without its change and a change never lands without its event, and
    drained by the API processes. All of a delivery's state is here, so it
    survives a restart. Plain strings rather than database enums, like the
    activity log: a new event type is a code change, not a migration.

    Deliveries are not recorded anywhere else (FR-11.14). A finished one is
    kept only until a newer finished one of the same webhook replaces it: what
    the owner is shown is the last delivery of each webhook (FR-11.11).
    """

    __table_args__ = (
        # What the loop asks for: pending rows that are due.
        Index("ix_webhookdelivery_state_next_attempt_at", "state", "next_attempt_at"),
        Index("ix_webhookdelivery_bot_user_id_webhook", "bot_user_id", "webhook"),
        CheckConstraint(
            "state IN ('pending', 'delivered', 'failed')",
            name="webhookdelivery_state",
        ),
        CheckConstraint(
            "webhook IN ('task', 'comment')", name="webhookdelivery_webhook"
        ),
    )

    # Also the delivery id the receiver is sent (FR-11.8).
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bot_user_id: uuid.UUID = Field(
        foreign_key="botuser.id", nullable=False, ondelete="CASCADE"
    )
    # Which of the bot user's two URLs this goes to. The URL itself is read
    # when the delivery is sent, so changing or clearing it reaches events
    # that are still waiting.
    webhook: str = Field(max_length=20)
    event: str = Field(max_length=20)
    # When the event happened, as the body says.
    occurred_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # What the body names. Taken when the event is recorded, so a retry sends
    # the title the event was about. A test event names no task.
    task_id: uuid.UUID | None = Field(default=None)
    task_title: str | None = Field(default=None, max_length=255)
    comment_id: uuid.UUID | None = Field(default=None)
    state: str = Field(default=DeliveryState.PENDING.value, max_length=20)
    # Attempts made so far; the schedule is read off it (FR-11.10).
    attempts: int = 0
    # When the loop may next try it. While one process holds it, this is
    # pushed out, so a crash mid-attempt only delays the retry.
    next_attempt_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_attempt_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_status_code: int | None = None
    last_error: str | None = Field(default=None, max_length=500)
    last_duration_ms: int | None = None


class WebhookUrl(SQLModel):
    """The address a webhook is set to: http or https (FR-11.3)."""

    url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2048)]


class WebhookDeliveryPublic(SQLModel):
    """
    A delivery as the owner sees it: when it was attempted, whether it
    succeeded, and the response status or the error (FR-11.11).
    """

    id: uuid.UUID
    event: WebhookEventType
    attempted_at: datetime
    # True once the receiver has answered with a 2xx.
    success: bool
    # Where it stands: delivered, still being retried, or failed after the last
    # attempt. A webhook is never disabled, however many fail.
    state: DeliveryState
    attempts: int
    status_code: int | None = None
    error: str | None = None
    duration_ms: int | None = None
    # When the next retry is due, while there is one.
    next_attempt_at: datetime | None = None


class WebhookPublic(SQLModel):
    # None while the webhook is not set.
    url: str | None = None
    last_delivery: WebhookDeliveryPublic | None = None


class BotWebhooks(SQLModel):
    task: WebhookPublic
    comment: WebhookPublic
    # Whether a secret exists. It is never reported again after it is shown.
    has_secret: bool
