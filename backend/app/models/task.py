"""
Tasks: the core entity, its recurring series, the queries that list it and the
batch inputs that change many at once (FR-01, FR-02, FR-06).
"""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints, model_validator
from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from .bot_user import BotUserRef
from .shared import get_datetime_utc
from .tag import TagName


class TaskPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TaskStatus(StrEnum):
    """
    Where a task stands (FR-01.4). Six fixed values rather than user-defined
    ones (ADR-0004, ADR-0008): every rule in the product only needs to know
    whether a task is open or done, and the five open values tell apart
    whether the work is decided on and who holds the next move. Declared in
    the order the interface lists them.

    A new task starts in `backlog`. A bot user hands finished work over by
    moving it to `review` and assigning it to the owner; entering review
    does not change the assignee on its own (FR-01.4a).
    """

    # Written down but not yet decided on. Where every new task starts.
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    # The doer has finished and the next move is the owner's: check the work
    # and close it, or send it back. How a bot user hands work over.
    REVIEW = "review"
    # Open, but the next move belongs to someone or something other than the
    # owner. Still open: waiting on a reply is not the work being finished.
    WAITING = "waiting"
    DONE = "done"


class TaskSort(StrEnum):
    """
    How a task list can be ordered, and which way round each one naturally
    runs when the request names no direction (FR-06.4).

    Due date means soonest first and priority means P1 first, because that is
    the work to reach for. Creation means newest first, because the reason to
    order by it is to see what has just arrived.
    """

    DUE_DATE = "due_date"
    PRIORITY = "priority"
    CREATED_AT = "created_at"


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
    status: TaskStatus | None = None
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
    # The direct subtasks of one task: the panel lists a task's children
    # without fetching the whole list to find them.
    parent_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    # The other half of the assignee filter: tasks with nobody on them.
    unassigned: bool = False
    # Tasks on any of the owner's bot users, whichever one: the question "how
    # much is with my integrations" without asking after each of them.
    assigned_to_bots: bool = False
    # Who filed the task: the owner, or one of their bot users, named by the
    # same id either way. It has no "unassigned" counterpart — every task has
    # a reporter (FR-01.29).
    reporter_id: uuid.UUID | None = None
    tag: str | None = None
    # Titles that contain this text, whatever its case (FR-06.14). Only the
    # title is searched. The spaces around the text are not part of it, and
    # blank text is refused rather than matching all.
    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    ) = None
    priority: TaskPriority | None = None
    # Any of the listed statuses matches; none listed means every status. A
    # list rather than an "open" flag, so a client can ask for exactly the
    # statuses it shows.
    status: list[TaskStatus] | None = None
    # An inclusive range: both ends are listed.
    due_from: date | None = None
    due_to: date | None = None
    # Open work whose due date has passed: a done task is never late, so this
    # filter leaves done out on its own. Narrowing further, to particular open
    # statuses, is the status filter's business.
    overdue: bool = False
    # Which side of the archive to list: live work by default, or only the
    # tasks of archived projects when the archive is asked for explicitly
    # (FR-05.14). Never both at once, so an archived task cannot slip into an
    # ordinary view through some other filter.
    archived: bool = False
    sort: TaskSort | None = None
    # Unset means each sort's own natural direction rather than ascending, so
    # asking for the created order plainly returns the newest first. Naming a
    # direction always wins, and the two orders that predate this both run
    # ascending naturally, so requests written before it mean what they did.
    order: SortOrder | None = None
    # Paging rides along with the rest of the query: FastAPI only unpacks a
    # query model when it is the whole of the endpoint's query.
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def check_assignee(self) -> TaskQuery:
        if self.unassigned and self.assignee_id is not None:
            raise ValueError("Ask for an assignee or for unassigned tasks, not both")
        if self.unassigned and self.assigned_to_bots:
            raise ValueError(
                "Ask for unassigned tasks or for tasks on bot users, not both"
            )
        return self


class SubtaskCompletion(StrEnum):
    """
    What a request that moves a task to done says about its open subtasks.

    Sending neither value is not a default: the request is refused, so a client
    never closes a parent without saying what happens below it (FR-02.6,
    FR-02.7). `complete` moves the subtasks to done; `leave_uncompleted` leaves
    each in the open status it has.
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
    an occurrence happened to be done (FR-01.13, FR-01.15).
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
    status: TaskStatus = TaskStatus.BACKLOG


# Properties to receive via API on update, all are optional
class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: TaskPriority | None = None
    project_id: uuid.UUID | None = None
    # The owner's id, or the id of one of the owner's bot users (FR-01.7).
    assignee_id: uuid.UUID | None = None
    status: TaskStatus | None = None
    # The task's tags in full: what is sent replaces what it had, and omitting
    # the field leaves them alone.
    tags: list[TagName] | None = None
    # A directive about the task's subtasks rather than a stored field: it is
    # only meaningful alongside `status: done`.
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
            postgresql_where=text("status <> 'done' AND deletion_id IS NULL"),
        ),
        # One assignee at most: the owner or a bot user, never both.
        CheckConstraint(
            "assignee_id IS NULL OR assignee_bot_user_id IS NULL",
            name="task_one_assignee",
        ),
        # Exactly one reporter, where the assignee allows neither: a task can
        # be nobody's to do, but never nobody's doing.
        CheckConstraint(
            "(reporter_id IS NULL) <> (reporter_bot_user_id IS NULL)",
            name="task_one_reporter",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    status: TaskStatus = Field(
        default=TaskStatus.BACKLOG,
        # Stored by value, so the partial index above reads the API's words.
        sa_type=SAEnum(  # type: ignore
            TaskStatus,
            name="taskstatus",
            values_callable=lambda members: [member.value for member in members],
        ),
    )
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
    # Who filed the task: its owner, or one of the owner's bot users. Exactly
    # one of the two is set — every task has an author, and a bot user's is
    # never recorded as its owner's (FR-01.29).
    #
    # Unlike the assignee, neither can be cleared: `SET NULL` would leave the
    # row failing its own constraint. Nor may either cascade — a bot user is
    # soft-deleted and stays named on what it filed (FR-08.19), so the link is
    # never exercised by a real delete, and must not be able to take the task
    # down with it if it ever were. The owner's own deletion already takes
    # their tasks through `owner_id`.
    reporter_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    reporter_bot_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="botuser.id", nullable=True
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


class TaskHandover(SQLModel):
    """
    How a task came to be in Review when a bot user put it there: which bot
    user handed its work over, and when (ADR-0008). Read off the activity
    log, so it names a deleted bot user as it was called.
    """

    bot_user: BotUserRef
    at: datetime


# Properties to return via API, id is always required
class TaskPublic(TaskBase):
    id: uuid.UUID
    status: TaskStatus
    # Always set: a subtask reports the project of its root ancestor.
    project_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    tags: list[str] = []
    # Whoever the task is assigned to: the owner, or a bot user. When it is a
    # bot user, `assignee_bot_user` says which, and whether it is deleted.
    assignee_id: uuid.UUID | None = None
    assignee_bot_user: BotUserRef | None = None
    # Who filed the task, in the same shape as the assignee, and always set.
    # Read-only: it names who made the request that created the task, and no
    # request body can set or change it.
    reporter_id: uuid.UUID | None = None
    reporter_bot_user: BotUserRef | None = None
    recurrence: Recurrence | None = None
    created_at: datetime | None = None
    # Its own subtasks, one level down, and how many of those are done: enough
    # for a list row to say "2/5" without fetching the tree.
    subtask_count: int = 0
    subtasks_done: int = 0
    # Set on a task in Review that a bot user moved there: the bot user's
    # hand-over of finished work (ADR-0008). Null when the owner made the
    # move, and on every task out of Review.
    handover: TaskHandover | None = None


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int
