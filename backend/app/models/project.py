"""
Projects: the containers tasks resolve to, archived or deleted as a whole
(FR-05).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from .shared import get_datetime_utc


# Shared properties
class ProjectBase(SQLModel):
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class ProjectCreate(ProjectBase):
    pass


# Properties to receive via API on update, all are optional
class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Project(ProjectBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    is_inbox: bool = False
    # Hidden from daily use and read-only, together with every task in it
    # (FR-05.10–FR-05.12). Tasks carry no flag of their own: a task is archived
    # exactly when the project it resolves to is, so archiving and unarchiving
    # are one write each way and nothing below the project can drift out of
    # step. Independent of deletion — an archived project can still be deleted.
    is_archived: bool = False
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    # Set once the project is deleted; None means it is live (FR-05.8).
    deletion_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="deletion.id",
        nullable=True,
        # Losing the event must not destroy what it marked: the row simply
        # becomes live again.
        ondelete="SET NULL",
        index=True,
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class ProjectPublic(ProjectBase):
    id: uuid.UUID
    is_inbox: bool
    is_archived: bool
    # The tasks resolving to it that are not deleted — what archiving takes out
    # of view and what deleting takes down with it (FR-05.9, FR-05.11).
    task_count: int = 0
    # What the Projects page says about the tasks, so it reads one list rather
    # than a list of tasks per project (FR-05.15). Subtasks count with their
    # root's project, like `task_count`; `open_count` is the number the task
    # list narrowed to the project shows, and `overdue_count`, `backlog_count`
    # and `review_count` are parts of it.
    open_count: int = 0
    overdue_count: int = 0
    backlog_count: int = 0
    review_count: int = 0
    done_count: int = 0
    created_at: datetime | None = None


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int
