"""
The activity log's one decoded shape (#299).

`ActivityEntry.details` is a JSONB column and stays one — this is a decoding
layer over it, not a migration. Before this module, eight readers in two
languages (`app.api.routes.activity`, `app.access`,
`app.repositories.activity`, `app.mcp.tools.search_activity`,
`app.mcp.tools.list_completions`, and three frontend files) each rediscovered
`details`' shape from `.get()` chains and casts over `dict[str, Any]`, with
nothing declaring that `task_count` present and `title` absent means a batch,
that a batch's `task_ids` holds strings, that a completion entry carries only
a title, or that a deletion entry carries its project because the live row
is gone.

Two things live here instead:

- One Pydantic model per `ActivityAction` (`_DETAIL_MODELS`), carrying
  exactly the fields that action's entry writes. `app.activity`, the only
  thing that writes entries, builds every entry's `details` by constructing
  one of these and dumping it (`encode`), so a field cannot reach the
  database without being declared on its action's model first. `decode` is
  the other direction: given a live entry, it rebuilds the same typed object
  from the stored dict, so a reader matches on a known shape instead of
  chaining `.get()` calls.
- The `details` key paths the kind filter (`app.activity_log`), the batch
  predicate (`app.access`) and the scope filter (`app.access`,
  `app.repositories.activity`) each quote, as named constants
  (`DETAILS_TASK_IDS` and friends), so the three spell the same key once
  rather than as separate string literals that could drift.
  `ACTIVITY_TASK_REF` (`app.models.activity`) is the same idea for the one
  key path that also backs a Postgres index, and stays there, exactly as
  spelled — this module imports it rather than respelling it.

ADR-0011's two assumptions become checkable here rather than conventional:
`TaskDeletedSingle`/`TaskRestoredSingle` declare `project` as part of a
deleted task's own shape — it carries the project because the live row is
gone and the project no longer lists it to find it by — and a batch
(`TaskDeletedBatch`, `TaskRestoredBatch`, `TasksBulkChangedDetails`) never
declares a `title` or any other per-task field, only a count and, for a bulk
change, the ids it named: there is no per-task slice of a batch to read out,
which is what "all-or-nothing" means at the type level.

`TaskDeletedBatch`/`TaskRestoredBatch` share their action's literal with
`TaskDeletedSingle`/`TaskRestoredSingle` (one deletion event, two shapes for
what it took down), so `decode` tells them apart the only way the data
itself does: by whether `title` is present — the same test every reader
used to run by hand, now run once.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.models.activity import ACTIVITY_TASK_REF as ACTIVITY_TASK_REF  # re-export
from app.models.activity import ActivityAction
from app.models.task import RecurrenceFrequency, TaskPriority, TaskStatus

# The `details` key names the kind filter, the batch predicate and the scope
# filter each quote (`app.activity_log`, `app.access`,
# `app.repositories.activity`), named once so the three cannot drift apart by
# a typo in a string literal.
DETAILS_TITLE = "title"
DETAILS_TASK = "task"
DETAILS_TASK_COUNT = "task_count"
DETAILS_TASK_IDS = "task_ids"
DETAILS_CHANGES = "changes"
DETAILS_STATUS = "status"
DETAILS_PROJECT = "project"


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")


class ProjectRef(_Base):
    """A project as an entry names it: its id and name at the time of the change."""

    id: uuid.UUID
    name: str | None = None


class AssigneeRef(_Base):
    """
    Who a task is assigned to: the user, or a bot user with its name — a bot
    user can be renamed or deleted later, the user is always "you". `name` is
    `None` for a user assignee, since there is only ever one user to be and
    naming it says nothing a reader does not already know; every reader
    already treats it as optional. (Before this module, a user assignee's
    `name` key was omitted outright rather than written as `null` — a wire
    detail no reader distinguished from `None`, and keeping the distinction
    would have cost `AssigneeRef` its declared shape in the generated client:
    a per-instance key omission cannot be expressed in a schema, only `{}`
    can, which is what every field that embeds `AssigneeRef` would have
    degraded to.)
    """

    type: Literal["user", "bot_user"]
    id: uuid.UUID
    name: str | None = None


class TaskRef(_Base):
    """What a comment or attachment entry names its task by."""

    id: uuid.UUID
    title: str


class RecurrenceRef(_Base):
    frequency: RecurrenceFrequency
    interval_days: int | None = None


class TaskSnapshot(_Base):
    """A task in full, as `task_created` records it (`app.activity._snapshot`)."""

    title: str
    description: str | None = None
    due_date: date | None = None
    priority: TaskPriority | None = None
    status: TaskStatus
    project: ProjectRef | None = None
    assignee_id: uuid.UUID | None = None
    assignee: AssigneeRef | None = None
    tags: tuple[str, ...] = ()
    recurrence: RecurrenceRef | None = None


class FieldChange(_Base):
    """One field's value before and after, as a `task_changed`/`project_changed`/
    `tag_renamed`/`comment_edited` entry's own `changes` map holds it."""

    # `from` is a Python keyword, so the field is named `from_` and aliased
    # back to `from` for both directions (`populate_by_name` on `_Base` lets
    # `decode` read either spelling; `encode` dumps `by_alias=True` so the
    # stored shape keeps the one every other reader already expects).
    from_: Any = Field(default=None, alias="from")
    to: Any = None


# --- Tasks -------------------------------------------------------------


class TaskCreatedDetails(_Base):
    title: str
    task: TaskSnapshot


class TaskChangedDetails(_Base):
    title: str
    # Keyed by field name (`title`, `description`, `due_date`, `priority`,
    # `tags`, `recurrence` — `app.activity._CHANGED_FIELDS`), each a
    # `{from, to}` pair whose own value type varies by field, so it is kept
    # as `Any` here rather than re-declared per field a second time.
    changes: dict[str, FieldChange]


class TaskMovedDetails(_Base):
    title: str
    from_project: ProjectRef | None = None
    to_project: ProjectRef | None = None


class TaskAssignedDetails(_Base):
    title: str
    assignee_id: uuid.UUID | None = None
    assignee: AssigneeRef | None = None
    previous_assignee_id: uuid.UUID | None = None
    previous_assignee: AssigneeRef | None = None


class TaskUnassignedDetails(_Base):
    title: str
    previous_assignee_id: uuid.UUID | None = None
    previous_assignee: AssigneeRef | None = None


class TaskCompletedDetails(_Base):
    """A completion entry carries only the task's title, recorded as it was
    titled the moment it closed — nothing else about the task is read from
    this entry (`app.mcp.tools.list_completions`' own reason: it is the one
    thing a deleted task's completion can still say)."""

    title: str


class TaskReopenedDetails(_Base):
    title: str
    to: TaskStatus


class TaskStatusChangedDetails(_Base):
    title: str
    from_: TaskStatus = Field(alias="from")
    to: TaskStatus


class TaskDeletedSingle(_Base):
    """
    One task's deletion. It carries its project (ADR-0011's first checkable
    assumption) because the live row is gone and the project no longer lists
    it to find it by, and `subtask_count` — what a restore of this event
    would bring back along with it.
    """

    title: str
    project: ProjectRef | None = None
    parent_id: uuid.UUID | None = None
    subtask_count: int = 0


class TaskDeletedBatch(_Base):
    """
    A batch's deletion: no single task to name, only the count — all-or-
    nothing (ADR-0011's second checkable assumption): there is no per-task
    slice of a batch to read out, only the selection that went down together.
    """

    task_count: int


class TaskRestoredSingle(_Base):
    title: str
    project: ProjectRef | None = None
    parent_id: uuid.UUID | None = None
    subtask_count: int = 0


class TaskRestoredBatch(_Base):
    task_count: int


class TasksBulkChangedDetails(_Base):
    """
    One act over many tasks (FR-10.9), named here rather than written one
    entry per task: `task_ids` holds the tasks it touched, as strings (the
    same spelling `app.access.activity_log_scope`'s own containment check
    and `app.repositories.activity`'s batch match compare against), and
    `changes` is the flat summary `app.api.routes.tasks._batch_summary`
    writes — new values, not `{from, to}` pairs, since a batch has no single
    "before" to report.
    """

    task_count: int
    task_ids: tuple[str, ...]
    changes: dict[str, Any]


# --- Projects ------------------------------------------------------------


class ProjectCreatedDetails(_Base):
    name: str
    description: str | None = None


class ProjectChangedDetails(_Base):
    name: str
    changes: dict[str, FieldChange]


class ProjectDeletedDetails(_Base):
    name: str
    task_count: int


class ProjectRestoredDetails(_Base):
    name: str
    task_count: int


# --- Comments and attachments ---------------------------------------------


class CommentAddedDetails(_Base):
    task: TaskRef
    body: str


class CommentEditedDetails(_Base):
    task: TaskRef
    changes: dict[str, FieldChange]


class CommentDeletedDetails(_Base):
    task: TaskRef
    body: str


class AttachmentAddedDetails(_Base):
    task: TaskRef
    filename: str
    content_type: str
    size: int


class AttachmentDeletedDetails(_Base):
    task: TaskRef
    filename: str
    content_type: str
    size: int


# --- Tags ------------------------------------------------------------------


class TagCreatedDetails(_Base):
    name: str


class TagRenamedDetails(_Base):
    name: str
    changes: dict[str, FieldChange]


class TagDeletedDetails(_Base):
    name: str
    task_count: int


class TagMergedDetails(_Base):
    name: str
    sources: tuple[str, ...]
    task_count: int


ActivityDetails = (
    TaskCreatedDetails
    | TaskChangedDetails
    | TaskMovedDetails
    | TaskAssignedDetails
    | TaskUnassignedDetails
    | TaskCompletedDetails
    | TaskReopenedDetails
    | TaskStatusChangedDetails
    | TaskDeletedSingle
    | TaskDeletedBatch
    | TaskRestoredSingle
    | TaskRestoredBatch
    | TasksBulkChangedDetails
    | ProjectCreatedDetails
    | ProjectChangedDetails
    | ProjectDeletedDetails
    | ProjectRestoredDetails
    | CommentAddedDetails
    | CommentEditedDetails
    | CommentDeletedDetails
    | AttachmentAddedDetails
    | AttachmentDeletedDetails
    | TagCreatedDetails
    | TagRenamedDetails
    | TagDeletedDetails
    | TagMergedDetails
)

# One model per action, for `decode` and for the writer's constructors
# (`app.activity`). `TASK_DELETED`/`TASK_RESTORED` map to a pair: `decode`
# picks between them by the one thing the data itself says — whether `title`
# is present (a batch never has one).
_DETAIL_MODELS: dict[
    ActivityAction, type[BaseModel] | tuple[type[BaseModel], type[BaseModel]]
] = {
    ActivityAction.TASK_CREATED: TaskCreatedDetails,
    ActivityAction.TASK_CHANGED: TaskChangedDetails,
    ActivityAction.TASK_MOVED: TaskMovedDetails,
    ActivityAction.TASK_ASSIGNED: TaskAssignedDetails,
    ActivityAction.TASK_UNASSIGNED: TaskUnassignedDetails,
    ActivityAction.TASK_COMPLETED: TaskCompletedDetails,
    ActivityAction.TASK_REOPENED: TaskReopenedDetails,
    ActivityAction.TASK_STATUS_CHANGED: TaskStatusChangedDetails,
    ActivityAction.TASK_DELETED: (TaskDeletedSingle, TaskDeletedBatch),
    ActivityAction.TASK_RESTORED: (TaskRestoredSingle, TaskRestoredBatch),
    ActivityAction.TASKS_BULK_CHANGED: TasksBulkChangedDetails,
    ActivityAction.PROJECT_CREATED: ProjectCreatedDetails,
    ActivityAction.PROJECT_CHANGED: ProjectChangedDetails,
    ActivityAction.PROJECT_DELETED: ProjectDeletedDetails,
    ActivityAction.PROJECT_RESTORED: ProjectRestoredDetails,
    ActivityAction.COMMENT_ADDED: CommentAddedDetails,
    ActivityAction.COMMENT_EDITED: CommentEditedDetails,
    ActivityAction.COMMENT_DELETED: CommentDeletedDetails,
    ActivityAction.ATTACHMENT_ADDED: AttachmentAddedDetails,
    ActivityAction.ATTACHMENT_DELETED: AttachmentDeletedDetails,
    ActivityAction.TAG_CREATED: TagCreatedDetails,
    ActivityAction.TAG_RENAMED: TagRenamedDetails,
    ActivityAction.TAG_DELETED: TagDeletedDetails,
    ActivityAction.TAG_MERGED: TagMergedDetails,
}

assert set(_DETAIL_MODELS) == set(ActivityAction), (
    "every action must declare the shape its entry writes"
)


def encode(details: BaseModel) -> dict[str, Any]:
    """
    A typed details object as `ActivityEntry.details` stores it: the writer's
    half of this module. `app.activity` calls this instead of handing a
    hand-built dict to `to_jsonable_python`, so a field cannot be written
    without first being declared on its action's model.
    """
    return details.model_dump(mode="json", by_alias=True)


def decode(action: str, details: dict[str, Any]) -> ActivityDetails:
    """
    `details` as the typed shape its action declares — the reader's half of
    this module. Raises like any other validation failure if a stored entry
    does not match its action's declared shape, which is the point: a new
    kind of entry that forgets to declare a field it writes fails loudly
    here instead of reading as silently absent everywhere else.
    """
    model = _DETAIL_MODELS[ActivityAction(action)]
    if isinstance(model, tuple):
        single, batch = model
        model = single if DETAILS_TITLE in details else batch
    return model.model_validate(  # type: ignore[return-value] # ty: ignore[invalid-return-type]
        details
    )


def named_task_ids(action: str, details: dict[str, Any]) -> list[uuid.UUID]:
    """
    The tasks an entry names: a batch's many (`tasks_bulk_changed`'s own
    `task_ids`), or none at all for a batched deletion/restore, which names
    no task — only `app.deletions.marked_task_ids` can say which rows a
    deletion event actually took down. Every other action is read by its own
    `entity_id`, which is the caller's job (this only answers for the one
    action whose details hold more than one task id).
    """
    if ActivityAction(action) is ActivityAction.TASKS_BULK_CHANGED:
        return [uuid.UUID(task_id) for task_id in details.get(DETAILS_TASK_IDS, [])]
    return []


# --- The public shape: the spike (#299) -------------------------------------
#
# Everything above is for `app.activity` (the writer) and Python readers.
# Below answers the ticket's own spike question — can the generated frontend
# client carry a discriminated union keyed on a string enum? — by being one:
# wired into `BotActivityEntryPublic.details` (`app.models.activity`), the
# real response `GET /activity-log/` sends a bot user, and read back from
# `scripts/generate-client.sh`'s own output (the PR body carries the
# generated snippet and the answer).
#
# Each action gets a "public" subclass that adds one field, `kind`: the
# discriminator the union keys on. For every action but two it is that
# action's own spelling. `task_deleted` and `task_restored` each write one of
# two shapes under the same action — a single task's own deletion, or a
# batch's, told apart only by whether `title` is present (`decode`'s own
# note above) — so a discriminator keyed on the action alone cannot tell the
# two parts of the union apart; `kind` splits them into
# `task_deleted`/`task_deleted_batch` and
# `task_restored`/`task_restored_batch` instead. `kind` is never written to
# the database: `to_public` injects it into a copy of `entry.details`, only
# for the one response that reads it this way.


class TaskCreatedDetailsPublic(TaskCreatedDetails):
    kind: Literal["task_created"] = "task_created"


class TaskChangedDetailsPublic(TaskChangedDetails):
    kind: Literal["task_changed"] = "task_changed"


class TaskMovedDetailsPublic(TaskMovedDetails):
    kind: Literal["task_moved"] = "task_moved"


class TaskAssignedDetailsPublic(TaskAssignedDetails):
    kind: Literal["task_assigned"] = "task_assigned"


class TaskUnassignedDetailsPublic(TaskUnassignedDetails):
    kind: Literal["task_unassigned"] = "task_unassigned"


class TaskCompletedDetailsPublic(TaskCompletedDetails):
    kind: Literal["task_completed"] = "task_completed"


class TaskReopenedDetailsPublic(TaskReopenedDetails):
    kind: Literal["task_reopened"] = "task_reopened"


class TaskStatusChangedDetailsPublic(TaskStatusChangedDetails):
    kind: Literal["task_status_changed"] = "task_status_changed"


class TaskDeletedSinglePublic(TaskDeletedSingle):
    kind: Literal["task_deleted"] = "task_deleted"


class TaskDeletedBatchPublic(TaskDeletedBatch):
    kind: Literal["task_deleted_batch"] = "task_deleted_batch"


class TaskRestoredSinglePublic(TaskRestoredSingle):
    kind: Literal["task_restored"] = "task_restored"


class TaskRestoredBatchPublic(TaskRestoredBatch):
    kind: Literal["task_restored_batch"] = "task_restored_batch"


class TasksBulkChangedDetailsPublic(TasksBulkChangedDetails):
    kind: Literal["tasks_bulk_changed"] = "tasks_bulk_changed"


class ProjectCreatedDetailsPublic(ProjectCreatedDetails):
    kind: Literal["project_created"] = "project_created"


class ProjectChangedDetailsPublic(ProjectChangedDetails):
    kind: Literal["project_changed"] = "project_changed"


class ProjectDeletedDetailsPublic(ProjectDeletedDetails):
    kind: Literal["project_deleted"] = "project_deleted"


class ProjectRestoredDetailsPublic(ProjectRestoredDetails):
    kind: Literal["project_restored"] = "project_restored"


class CommentAddedDetailsPublic(CommentAddedDetails):
    kind: Literal["comment_added"] = "comment_added"


class CommentEditedDetailsPublic(CommentEditedDetails):
    kind: Literal["comment_edited"] = "comment_edited"


class CommentDeletedDetailsPublic(CommentDeletedDetails):
    kind: Literal["comment_deleted"] = "comment_deleted"


class AttachmentAddedDetailsPublic(AttachmentAddedDetails):
    kind: Literal["attachment_added"] = "attachment_added"


class AttachmentDeletedDetailsPublic(AttachmentDeletedDetails):
    kind: Literal["attachment_deleted"] = "attachment_deleted"


class TagCreatedDetailsPublic(TagCreatedDetails):
    kind: Literal["tag_created"] = "tag_created"


class TagRenamedDetailsPublic(TagRenamedDetails):
    kind: Literal["tag_renamed"] = "tag_renamed"


class TagDeletedDetailsPublic(TagDeletedDetails):
    kind: Literal["tag_deleted"] = "tag_deleted"


class TagMergedDetailsPublic(TagMergedDetails):
    kind: Literal["tag_merged"] = "tag_merged"


ActivityDetailsPublic = Annotated[
    TaskCreatedDetailsPublic
    | TaskChangedDetailsPublic
    | TaskMovedDetailsPublic
    | TaskAssignedDetailsPublic
    | TaskUnassignedDetailsPublic
    | TaskCompletedDetailsPublic
    | TaskReopenedDetailsPublic
    | TaskStatusChangedDetailsPublic
    | TaskDeletedSinglePublic
    | TaskDeletedBatchPublic
    | TaskRestoredSinglePublic
    | TaskRestoredBatchPublic
    | TasksBulkChangedDetailsPublic
    | ProjectCreatedDetailsPublic
    | ProjectChangedDetailsPublic
    | ProjectDeletedDetailsPublic
    | ProjectRestoredDetailsPublic
    | CommentAddedDetailsPublic
    | CommentEditedDetailsPublic
    | CommentDeletedDetailsPublic
    | AttachmentAddedDetailsPublic
    | AttachmentDeletedDetailsPublic
    | TagCreatedDetailsPublic
    | TagRenamedDetailsPublic
    | TagDeletedDetailsPublic
    | TagMergedDetailsPublic,
    Field(discriminator="kind"),
]


def public_kind(action: str, details: dict[str, Any]) -> str:
    """
    The `kind` `to_public` injects: an action's own spelling, except for
    `task_deleted`/`task_restored`, split into a `..._batch` kind the same
    way `decode` tells the two shapes apart — by whether `title` is present.
    """
    resolved = ActivityAction(action)
    if resolved in (ActivityAction.TASK_DELETED, ActivityAction.TASK_RESTORED):
        return resolved.value if DETAILS_TITLE in details else f"{resolved.value}_batch"
    return resolved.value


def to_public(action: str, details: dict[str, Any]) -> dict[str, Any]:
    """
    `details` with its `kind` discriminator injected, ready to validate
    against `ActivityDetailsPublic` — never stored, only read.
    """
    return {**details, "kind": public_kind(action, details)}
