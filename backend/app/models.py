import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import EmailStr, StringConstraints, model_validator
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Identity,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
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


class TaskBulkUpdate(SQLModel):
    """
    One set of changes for many tasks: the single-task update, plus the tasks
    it applies to.

    `add_tags` and `remove_tags` rather than `tags`: a batch adds a label to a
    selection or takes one off it, and replacing every task's tags wholesale
    would destroy what each of them already carried.
    """

    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    completed: bool | None = None
    subtasks: SubtaskCompletion | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    project_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    add_tags: list[TagName] = []
    remove_tags: list[TagName] = []


class TaskBulkDelete(SQLModel):
    """
    One deletion event over several tasks, restorable as the one act it was.
    """

    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    delete_subtasks: bool = False


class TaskRefusal(SQLModel):
    """One task a batch could not change, and what stood in the way."""

    task_id: uuid.UUID
    code: str
    message: str


class BulkResult(SQLModel):
    """How many tasks one act changed."""

    updated: int = 0
    deleted: int = 0


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
    # Which side of the archive to list: live work by default, or only the
    # tasks of archived projects when the archive is asked for explicitly
    # (FR-05.14). Never both at once, so an archived task cannot slip into an
    # ordinary view through some other filter.
    archived: bool = False
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


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    EVERY_N_DAYS = "every_n_days"


# The shortest "every N days" rule. Every one day is the daily rule spelt a
# second way, and one rule gets one spelling. Published in the API schema, which
# is where the web client reads it from.
MIN_INTERVAL_DAYS = 2


class Recurrence(SQLModel):
    """
    How often a recurring task comes back: a fixed interval, never tied to when
    an occurrence happened to be completed (FR-01.13, FR-01.15).
    """

    frequency: RecurrenceFrequency
    # The N of "every N days"; no other frequency takes one.
    interval_days: int | None = Field(default=None, ge=MIN_INTERVAL_DAYS)

    @model_validator(mode="after")
    def check_interval_days(self) -> Recurrence:
        needs_days = self.frequency is RecurrenceFrequency.EVERY_N_DAYS
        if needs_days and self.interval_days is None:
            raise ValueError("Every N days needs `interval_days`")
        if not needs_days and self.interval_days is not None:
            raise ValueError("`interval_days` only applies to every N days")
        return self


class DueDateScope(StrEnum):
    """
    What moving the due date of an open recurring occurrence means for the rest
    of its series.

    There is no default: a client that changes the date without saying which
    one is refused, so a series is never rescheduled by omission (FR-01.17).
    """

    # Moves this task only; the series keeps its schedule (FR-01.18).
    THIS_OCCURRENCE = "this_occurrence"
    # Moves this task and the schedule every later occurrence follows
    # (FR-01.19).
    THIS_AND_FOLLOWING = "this_and_following"


class Series(SQLModel, table=True):
    """
    The occurrences of one recurring task, and the schedule they follow.

    Each occurrence is a task of its own (ADR-0001) with a step number: the
    first is step 0, and completing step k creates step k+1. Its due date is
    worked out from the schedule anchor rather than from the previous
    occurrence's date, so moving one occurrence alone does not drift the rest
    (FR-01.18), and a monthly series that starts on the 31st comes back to the
    31st whenever the month has one.
    """

    __table_args__ = (
        CheckConstraint(
            "(frequency = 'every_n_days') = (interval_days IS NOT NULL)",
            name="series_interval_days_for_every_n_days",
        ),
        CheckConstraint(
            f"interval_days >= {MIN_INTERVAL_DAYS}",
            name="series_interval_days_minimum",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    frequency: RecurrenceFrequency = Field(
        # Stored by value, so the check above reads the same words the API uses.
        sa_type=SAEnum(  # type: ignore
            RecurrenceFrequency,
            name="recurrencefrequency",
            values_callable=lambda members: [member.value for member in members],
        )
    )
    interval_days: int | None = None
    # The schedule: step `anchor_step` falls due on `anchor_date`, and every
    # other step is a whole number of intervals away from it. Rescheduling "this
    # and all following" moves the anchor to the occurrence being edited.
    anchor_date: date
    anchor_step: int = 0
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


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
    # The owner's id, or the id of one of the owner's bot users (FR-01.7).
    assignee_id: uuid.UUID | None = None
    recurrence: Recurrence | None = None


# Properties to receive via API on update, all are optional
class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: TaskPriority | None = None
    project_id: uuid.UUID | None = None
    # The owner's id, or the id of one of the owner's bot users (FR-01.7).
    assignee_id: uuid.UUID | None = None
    completed: bool | None = None
    # The task's tags in full: what is sent replaces what it had, and omitting
    # the field leaves them alone.
    tags: list[TagName] | None = None
    # A directive about the task's subtasks rather than a stored field: it is
    # only meaningful alongside `completed: true`.
    subtasks: SubtaskCompletion | None = None
    # `null` stops the task recurring; omitting the field leaves it alone.
    recurrence: Recurrence | None = None
    # Another directive: required when the due date of an open recurring
    # occurrence changes, and refused anywhere else.
    due_date_scope: DueDateScope | None = None


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
        CheckConstraint(
            "(series_id IS NULL) = (series_step IS NULL)",
            name="task_series_step_with_series",
        ),
        # At most one open occurrence per series (FR-01.16), held by the
        # database rather than by every code path that completes, reopens or
        # creates a task remembering to check.
        Index(
            "ix_task_one_open_occurrence",
            "series_id",
            unique=True,
            postgresql_where=text("NOT completed AND deletion_id IS NULL"),
        ),
        # One assignee at most: the owner or a bot user, never both.
        CheckConstraint(
            "assignee_id IS NULL OR assignee_bot_user_id IS NULL",
            name="task_one_assignee",
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
    # Who is responsible for the task: its owner, or one of the owner's bot
    # users. At most one of the two is set; neither means nobody (FR-01.6).
    assignee_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="SET NULL"
    )
    assignee_bot_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="botuser.id", nullable=True, ondelete="SET NULL"
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
    # Set on every occurrence of a recurring task, with its place in the series.
    series_id: uuid.UUID | None = Field(
        default=None, foreign_key="series.id", nullable=True, index=True
    )
    series_step: int | None = None
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class BotUserRef(SQLModel):
    """
    A bot user as a task or comment names it: the one it is assigned to, or
    the one that wrote it. A deleted bot user stays on what it was given and
    what it wrote (FR-08.19, FR-08.21), marked deleted.
    """

    id: uuid.UUID
    name: str
    deleted: bool


# Properties to return via API, id is always required
class TaskPublic(TaskBase):
    id: uuid.UUID
    completed: bool
    # Always set: a subtask reports the project of its root ancestor.
    project_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    tags: list[str] = []
    # Whoever the task is assigned to: the owner, or a bot user. When it is a
    # bot user, `assignee_bot_user` says which, and whether it is deleted.
    assignee_id: uuid.UUID | None = None
    assignee_bot_user: BotUserRef | None = None
    recurrence: Recurrence | None = None
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


class AttachmentBase(SQLModel):
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=255)
    # A plain Integer caps out at 2 GiB, well within reach once
    # ATTACHMENT_MAX_SIZE_BYTES is raised for a deployment that wants larger
    # files.
    size: int = Field(sa_type=BigInteger)


class Attachment(AttachmentBase, table=True):
    """
    A file attached to a task (FR-04.1). Only the metadata lives here; the
    bytes sit behind the storage interface (ADR-0002), keyed by this row's
    id, so nothing here assumes where or how they are actually stored.

    Deleting the task this points at only soft-deletes the task (FR-01.8):
    this row and the bytes it names are left alone, so a restored task comes
    back with its files.
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


class AttachmentPublic(AttachmentBase):
    id: uuid.UUID
    task_id: uuid.UUID
    created_at: datetime | None = None


class AttachmentsPublic(SQLModel):
    data: list[AttachmentPublic]
    count: int


class ActivityAction(StrEnum):
    """Everything the activity log records (FR-10.3)."""

    TASK_CREATED = "task_created"
    TASK_CHANGED = "task_changed"
    # Many tasks changed by one act: one entry for the batch, not one per task.
    TASKS_BULK_CHANGED = "tasks_bulk_changed"
    TASK_COMPLETED = "task_completed"
    TASK_REOPENED = "task_reopened"
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


class ActivityEntityType(StrEnum):
    TASK = "task"
    PROJECT = "project"
    COMMENT = "comment"
    ATTACHMENT = "attachment"
    TAG = "tag"


class ActivityEntry(SQLModel, table=True):
    """
    One change in a user's account, and who made it (FR-10.1, FR-10.2).

    Append-only and kept indefinitely (FR-10.5). An entry describes its change
    in full in `details`, so it still reads after the entity is gone: nothing
    here points at the entity with a foreign key, only names it.
    """

    __table_args__ = (
        # A user's log, newest first, is the only way entries are read.
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


class ActivityEntryPublic(SQLModel):
    id: uuid.UUID
    action: ActivityAction
    entity_type: ActivityEntityType
    entity_id: uuid.UUID
    # Exactly one of the two is set. A bot user's name comes along, since the
    # log is where its owner finds out which integration did what.
    actor_id: uuid.UUID | None = None
    actor_bot_user_id: uuid.UUID | None = None
    actor_bot_user_name: str | None = None
    deletion_id: uuid.UUID | None = None
    details: dict[str, Any]
    created_at: datetime | None = None
    # Whether the entity can still be opened, and the project to open it in:
    # a deleted task has nowhere to link to.
    entity_exists: bool
    entity_project_id: uuid.UUID | None = None
    # Set on a deletion entry whose rows are still deleted: the entry a
    # restore can be started from.
    restorable: bool = False


class ActivityEntriesPublic(SQLModel):
    data: list[ActivityEntryPublic]
    count: int


BotUserName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


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


class BotScope(SQLModel):
    """
    Where a bot user may act and what it may do there.

    The projects are always named one by one: there is no value meaning "all
    projects" (FR-08.6), so a project created tomorrow is never in the scope
    of a bot set up today.
    """

    project_ids: list[uuid.UUID]
    permissions: BotPermissions


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

    Not a kind of `User`: login, registration, password reset and the
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
    # Whether a token is out, revoked or not; the token itself is never
    # reported again. One that has expired is still out until it is revoked.
    has_token: bool
    token_issued_at: datetime | None = None
    token_expires_at: datetime | None = None
    token_last_used_at: datetime | None = None
    token_revoked_at: datetime | None = None
    created_at: datetime | None = None


class BotUsersPublic(SQLModel):
    data: list[BotUserPublic]
    count: int


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
