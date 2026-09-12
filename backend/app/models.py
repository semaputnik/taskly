import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import EmailStr
from sqlalchemy import CheckConstraint, DateTime
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


class TaskPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


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
    assignee_id: uuid.UUID | None = None
    created_at: datetime | None = None


class TasksPublic(SQLModel):
    data: list[TaskPublic]
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
