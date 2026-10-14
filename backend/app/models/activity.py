"""
The activity log: one append-only entry per change, read from either end and
narrowed by kind (FR-10).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Identity,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from .shared import get_datetime_utc


class ActivityAction(StrEnum):
    """Everything the activity log records (FR-10.3)."""

    TASK_CREATED = "task_created"
    TASK_CHANGED = "task_changed"
    # Many tasks changed by one act: one entry for the batch, not one per task.
    TASKS_BULK_CHANGED = "tasks_bulk_changed"
    TASK_COMPLETED = "task_completed"
    TASK_REOPENED = "task_reopened"
    # A move between open statuses; a move to or out of done is completed or
    # reopened, so an entry never says both.
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_DELETED = "task_deleted"
    TASK_RESTORED = "task_restored"
    TASK_MOVED = "task_moved"
    TASK_ASSIGNED = "task_assigned"
    TASK_UNASSIGNED = "task_unassigned"
    PROJECT_CREATED = "project_created"
    PROJECT_CHANGED = "project_changed"
    PROJECT_DELETED = "project_deleted"
    PROJECT_RESTORED = "project_restored"
    COMMENT_ADDED = "comment_added"
    COMMENT_EDITED = "comment_edited"
    COMMENT_DELETED = "comment_deleted"
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_DELETED = "attachment_deleted"
    TAG_CREATED = "tag_created"
    TAG_RENAMED = "tag_renamed"
    TAG_DELETED = "tag_deleted"
    # Several tags folded into one: one entry naming both sides, not one per
    # task that changed or per tag that went.
    TAG_MERGED = "tag_merged"


class ActivityKind(StrEnum):
    """
    How a reader groups the log's actions in order to narrow it.

    Coarser than `ActivityAction` on purpose: someone asks the log what they
    finished, filed or threw away — not which of two dozen action names an
    entry happens to carry. The groups do not overlap, so an entry answers to
    exactly one of them and a reader never meets the same change twice.

    The grouping is the server's rather than a set of actions the client
    sends, because `COMPLETED` is not a set of actions at all: closing tasks
    in a batch writes one `TASKS_BULK_CHANGED` entry naming the new status,
    not a completion per task, so the group has to read that entry's details.
    """

    COMPLETED = "completed"
    CREATED = "created"
    CHANGED = "changed"
    DELETED = "deleted"
    COMMENTS = "comments"
    TAGS = "tags"


class ActivityOrder(StrEnum):
    """Which end of the log a read starts from (FR-10.10)."""

    NEWEST = "newest"
    OLDEST = "oldest"


class ActivityEntityType(StrEnum):
    TASK = "task"
    PROJECT = "project"
    COMMENT = "comment"
    ATTACHMENT = "attachment"
    TAG = "tag"


# What a comment or attachment entry names its task by. Spelled out as SQL so
# the index below and the filter that reads it are exactly one expression: a
# bound path would leave the planner unable to match the two. (The migration
# that created the index spells it out again, as a migration must.)
#
# Cast explicitly to `text`, matching the spelling Postgres normalizes this
# expression to once the index exists (confirmed against a database at head
# with `SELECT indexdef FROM pg_indexes`): without the casts here,
# `alembic revision --autogenerate` reads the stored index as having changed
# and proposes dropping and recreating it, on every run (#293). The casts are
# a no-op for `->` and `->>`, which already take and return `text`, so this
# changes no behaviour of the index or of the filters that share it.
ACTIVITY_TASK_REF = "((details -> 'task'::text) ->> 'id'::text)"


class ActivityEntry(SQLModel, table=True):
    """
    One change in a user's account, and who made it (FR-10.1, FR-10.2).

    Append-only and kept indefinitely (FR-10.5). An entry describes its change
    in full in `details`, so it still reads after the entity is gone: nothing
    here points at the entity with a foreign key, only names it.
    """

    __table_args__ = (
        # A user's log is read from either end (FR-10.10); the index serves
        # both directions.
        Index("ix_activityentry_owner_id_position", "owner_id", "position"),
        # One bot user's own feed, newest first. Without it, reading a quiet
        # bot user means walking a log that is kept for ever (FR-10.5) until
        # its few entries turn up.
        Index(
            "ix_activityentry_owner_id_actor_bot_user_id_position",
            "owner_id",
            "actor_bot_user_id",
            "position",
        ),
        # One kind of change, newest first. Same reasoning as the feed above:
        # a log kept for ever (FR-10.5) must not be walked end to end to find
        # the handful of entries a narrow kind gathers.
        Index(
            "ix_activityentry_owner_id_action_position",
            "owner_id",
            "action",
            "position",
        ),
        # One task's history: what happened to it, and to the comments and
        # files on it, which name it in their details rather than pointing at
        # it. The panel of a task reads this every time it opens.
        Index("ix_activityentry_owner_id_entity_id", "owner_id", "entity_id"),
        Index(
            "ix_activityentry_owner_id_task",
            "owner_id",
            text(ACTIVITY_TASK_REF),
        ),
        # A change is made by exactly one actor: a user, or a bot user.
        CheckConstraint(
            "(actor_id IS NULL) <> (actor_bot_user_id IS NULL)",
            name="activityentry_one_actor",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Orders entries exactly, including the several one request can write
    # within the same instant.
    position: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), nullable=False),
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    # Who made the change (FR-10.2): the user it was made by, or the bot user.
    # Exactly one is set, so a bot's change is never attributed to its owner,
    # and an entry naming a user means what it always has.
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="CASCADE"
    )
    actor_bot_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="botuser.id", nullable=True, ondelete="CASCADE"
    )
    # Plain strings rather than a database enum, so a new kind of entry is a
    # code change and not a migration.
    action: str = Field(max_length=50)
    entity_type: str = Field(max_length=50)
    entity_id: uuid.UUID
    # Set on the entry for a deletion: the event a restore brings back.
    deletion_id: uuid.UUID | None = Field(
        default=None, foreign_key="deletion.id", nullable=True, ondelete="SET NULL"
    )
    details: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Imported here rather than at the top of the file: `app.activity_details`
# imports `ActivityAction`/`ActivityEntityType`/`ACTIVITY_TASK_REF` back from
# this module, so this has to wait until all three already exist on it
# (#299's own spike — see `app.activity_details`'s own module docstring for
# what this union answers and how).
from app.activity_details import ActivityDetailsPublic  # noqa: E402


class BotActivityEntryPublic(SQLModel):
    """
    What a bot user's own read of the activity log carries (#298, ADR-0011):
    everything a human's read does except `restorable` and the deletion id.
    Restoring stays a human-only action, and a handle a bot user cannot act
    on is a field worth withholding from its response, not a dead one worth
    keeping at `False`/`None` — so this is the base shape, and
    `ActivityEntryPublic` is the one that adds the two restore-related
    fields back for a human, rather than the other way around.
    """

    id: uuid.UUID
    action: ActivityAction
    entity_type: ActivityEntityType
    entity_id: uuid.UUID
    # Exactly one of the two is set. A bot user's name comes along, since the
    # log is where its owner finds out which integration did what.
    actor_id: uuid.UUID | None = None
    actor_bot_user_id: uuid.UUID | None = None
    actor_bot_user_name: str | None = None
    # A discriminated union keyed on `kind` (`app.activity_details.to_public`
    # injects it; never stored), not the plain `dict[str, Any]` the database
    # column (`ActivityEntry.details`, above) holds — #299's spike.
    details: ActivityDetailsPublic
    created_at: datetime | None = None
    # Whether the entity can still be opened, and the project to open it in:
    # a deleted task has nowhere to link to.
    entity_exists: bool
    entity_project_id: uuid.UUID | None = None


class ActivityEntryPublic(BotActivityEntryPublic):
    # Set on a deletion entry whose rows are still deleted: the entry a
    # restore can be started from. A bot user's response carries neither
    # this nor `deletion_id` (ADR-0011) — see `BotActivityEntryPublic`.
    deletion_id: uuid.UUID | None = None
    restorable: bool = False


class ActivityEntriesPublic(SQLModel):
    data: list[ActivityEntryPublic]
    count: int


class BotActivityEntriesPublic(SQLModel):
    data: list[BotActivityEntryPublic]
    count: int
