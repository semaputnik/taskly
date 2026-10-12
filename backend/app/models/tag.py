"""
Tags: the labels a user puts on tasks, and the task-tag link (FR-01.20-FR-01.28).
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints
from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from .bot_user import BotUserRef
from .shared import get_datetime_utc

# A tag name as it arrives from a client: trimmed first, so a name of nothing
# but spaces is rejected rather than stored blank.
TagName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class TagBase(SQLModel):
    name: str = Field(max_length=50)


class Tag(TagBase, table=True):
    """
    A named label a user puts on tasks.

    Tags belong to the user rather than to a project, so one means the same
    thing across their whole account and can gather work that crosses projects
    (FR-01.21). A tag is created on its own or by typing a new name onto a task
    (FR-01.20), and stays until it is deleted, whether or not any task carries
    it (FR-01.23). Tasks point at it by key, so renaming it renames it on every
    task, and deleting it takes it off every task (FR-01.24, FR-01.25).
    """

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="tag_owner_id_name_key"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TaskTag(SQLModel, table=True):
    """Which tags are on which tasks."""

    task_id: uuid.UUID = Field(
        foreign_key="task.id", primary_key=True, ondelete="CASCADE"
    )
    tag_id: uuid.UUID = Field(
        foreign_key="tag.id", primary_key=True, ondelete="CASCADE"
    )


class TagCreate(SQLModel):
    name: TagName


class TagUpdate(SQLModel):
    name: TagName


class TagPublic(TagBase):
    id: uuid.UUID
    # The live tasks carrying it — not deleted, not archived with their
    # project: exactly what the task list filtered by the tag shows (FR-01.26).
    task_count: int = 0
    # The tasks carrying it that are archived with their project. Not in the
    # list, but deleting or merging the tag reaches them too.
    archived_task_count: int = 0
    # The bot user that brought the tag into being, if one did — through the
    # API or by typing a new name onto a task — so a bot user's vocabulary can
    # be told from the user's own (FR-01.28).
    created_by_bot_user: BotUserRef | None = None
    created_at: datetime | None = None


class TagDuplicateDismissal(SQLModel, table=True):
    """
    A group of likely duplicate tags the user said to stop offering
    (FR-01.28).

    The group is remembered by its members exactly as they were — each id with
    the name it had — so renaming one of them, or a new spelling joining them,
    makes it a different group, offered again.
    """

    __table_args__ = (
        UniqueConstraint(
            "owner_id", "signature", name="tagduplicatedismissal_owner_signature_key"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    # A digest of the members, ids and names, in a fixed order.
    signature: str = Field(max_length=64)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TagDuplicateGroup(SQLModel):
    """Tags whose names differ only in form: a suggestion to merge them."""

    tags: list[TagPublic]


class TagDuplicateGroups(SQLModel):
    data: list[TagDuplicateGroup]


class TagDuplicateDismiss(SQLModel):
    """Every member of the group to stop offering, and nothing else."""

    tag_ids: list[uuid.UUID] = Field(min_length=2)


class TagMerge(SQLModel):
    """The tags to fold into the one the merge is addressed to."""

    source_ids: list[uuid.UUID] = Field(min_length=1)


class TagMergePreview(SQLModel):
    """
    What a merge would move: the tasks carrying any of the sources, each
    counted once, live and archived apart (FR-01.27).
    """

    task_count: int
    archived_task_count: int


class TagsPublic(SQLModel):
    data: list[TagPublic]
    count: int
