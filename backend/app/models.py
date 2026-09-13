import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import EmailStr, StringConstraints, model_validator
from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


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
        # went down as a cascade.
        CheckConstraint(
            "(task_id IS NULL) <> (project_id IS NULL)",
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
    created_at: datetime | None = None


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int


# A tag name as it arrives from a client: trimmed first, so a name of nothing
# but spaces is rejected rather than stored blank.
TagName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class TagBase(SQLModel):
    name: str = Field(max_length=50)


class Tag(TagBase, table=True):
    """
    A free-text label a user puts on tasks.

    Tags belong to the user rather than to a project, so one means the same
    thing across their whole account and can gather work that crosses projects
    (FR-01.21). There is no screen for managing them: a tag comes into being by
    being typed onto a task (FR-01.20).
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


class TagPublic(TagBase):
    id: uuid.UUID


class TagsPublic(SQLModel):
    data: list[TagPublic]
    count: int


class TaskPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TaskSort(StrEnum):
    DUE_DATE = "due_date"
    PRIORITY = "priority"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class TaskQuery(SQLModel):
    """
    How a task list is narrowed and ordered.

    Every filter that is set has to match: a task is listed only if it
    satisfies all of them, so adding one always narrows the result (FR-06.3).
    """

    # A subtask holds no project of its own, so this matches on the project the
    # task resolves to, not on the column.
    project_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    # The other half of the assignee filter: tasks with nobody on them.
    unassigned: bool = False
    tag: str | None = None
    priority: TaskPriority | None = None
    completed: bool | None = None
    # An inclusive range: both ends are listed.
    due_from: date | None = None
    due_to: date | None = None
    # Work whose due date has passed. Whether it is finished is the
    # completion filter's business: every filter owns one dimension, so they
    # can be combined without one quietly overriding another.
    overdue: bool = False
    sort: TaskSort | None = None
    order: SortOrder = SortOrder.ASC
    # Paging rides along with the rest of the query: FastAPI only unpacks a
    # query model when it is the whole of the endpoint's query.
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def check_assignee(self) -> TaskQuery:
        if self.unassigned and self.assignee_id is not None:
            raise ValueError("Ask for an assignee or for unassigned tasks, not both")
        return self


class SubtaskCompletion(StrEnum):
    """
    What a completion request says about the task's uncompleted subtasks.

    Sending neither value is not a default: the request is refused, so a client
    never completes a parent without saying what happens below it (FR-02.6,
    FR-02.7).
    """

    LEAVE_UNCOMPLETED = "leave_uncompleted"
    COMPLETE = "complete"


# Shared properties
class TaskBase(SQLModel):
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    # Date only, no time of day: storing a timestamp would let timezone
    # conversion shift the date the user actually picked.
    due_date: date | None = None
    priority: TaskPriority | None = None


# Properties to receive via API on creation
class TaskCreate(TaskBase):
    # Tag names, created on the fly if the user hasn't used them before.
    tags: list[TagName] = []
    # None lands the task in the user's Inbox (FR-05.4). A subtask takes its
    # parent's project instead, so the two fields are mutually exclusive.
    project_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    # Only the task owner is a valid assignee for now; bot users become
    # assignable in semaputnik/taskly#7 without needing to reshape this field.
    assignee_id: uuid.UUID | None = None


# Properties to receive via API on update, all are optional
class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: TaskPriority | None = None
    project_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    completed: bool | None = None
    # The task's tags in full: what is sent replaces what it had, and omitting
    # the field leaves them alone.
    tags: list[TagName] | None = None
    # A directive about the task's subtasks rather than a stored field: it is
    # only meaningful alongside `completed: true`.
    subtasks: SubtaskCompletion | None = None


# Database model, database table inferred from class name
class Task(TaskBase, table=True):
    __table_args__ = (
        # A task is either a root task with a project or a subtask that derives
        # one from its root ancestor — never both, and never neither. Keeping
        # the project off subtasks makes moving a whole tree a single write and
        # leaves no room for a subtask to drift into another project (FR-02.4).
        CheckConstraint(
            "(parent_id IS NULL) <> (project_id IS NULL)",
            name="task_root_has_project",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    completed: bool = False
    parent_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="task.id",
        nullable=True,
        ondelete="CASCADE",
        index=True,
    )
    project_id: uuid.UUID | None = Field(
        default=None, foreign_key="project.id", nullable=True, ondelete="CASCADE"
    )
    # Denormalized from the project's owner at creation time, so ownership
    # checks and per-user listings don't need a join.
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    assignee_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="SET NULL"
    )
    # Set once the task is deleted; None means it is live (FR-01.8).
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
class TaskPublic(TaskBase):
    id: uuid.UUID
    completed: bool
    # Always set: a subtask reports the project of its root ancestor.
    project_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    tags: list[str] = []
    assignee_id: uuid.UUID | None = None
    created_at: datetime | None = None


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int


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
    narrative (FR-03.1) — also the channel a bot user will report back
    through once it can write here (semaputnik/taskly#7).

    A comment carries no attachment relation of its own (FR-03.3): the schema
    simply offers none, rather than a validation rule turning one away.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        foreign_key="task.id", nullable=False, ondelete="CASCADE", index=True
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class CommentPublic(CommentBase):
    id: uuid.UUID
    task_id: uuid.UUID
    created_at: datetime | None = None


class CommentsPublic(SQLModel):
    data: list[CommentPublic]
    count: int


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


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
