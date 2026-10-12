"""
Comments: the running note on a task's thread (FR-03).
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from .bot_user import BotUserRef
from .shared import get_datetime_utc

# A comment's text as it arrives from a client: trimmed first, and never
# blank, so a running note always has something to say.
CommentBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
]


class CommentBase(SQLModel):
    body: str = Field(max_length=10000)


class CommentCreate(SQLModel):
    body: CommentBody


class CommentUpdate(SQLModel):
    body: CommentBody


class Comment(CommentBase, table=True):
    """
    A note on a task's thread, read oldest-first so the history reads as a
    narrative (FR-03.1) — also the channel a bot user reports back through.

    A comment carries no attachment relation of its own (FR-03.3): the schema
    simply offers none, rather than a validation rule turning one away.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        foreign_key="task.id", nullable=False, ondelete="CASCADE", index=True
    )
    # The user whose task this is. A comment written by one of their bot users
    # still belongs to them; `author_bot_user_id` then says which bot wrote it.
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    author_bot_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="botuser.id", nullable=True, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class CommentPublic(CommentBase):
    id: uuid.UUID
    task_id: uuid.UUID
    # Set when a bot user wrote the comment; None means the user did.
    author_bot_user: BotUserRef | None = None
    created_at: datetime | None = None


class CommentsPublic(SQLModel):
    data: list[CommentPublic]
    count: int
