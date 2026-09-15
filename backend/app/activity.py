"""
The activity log's single write point.

Every change reaches the database through a session flush, so that is where
the log listens, rather than in each route: an endpoint added tomorrow is
logged without having to remember to be (semaputnik/taskly#8).

A transaction is logged in two steps. Before each flush, the tasks the flush is
about to change have their state read from the database — that is still the
state before the change. Just before commit, the same tasks are read again, the
two are compared, and the entries go into the very transaction being committed:
a change never lands without its entry, and an entry never lands without its
change.

Reading whole states rather than watching individual attributes is what lets
one mechanism see every way a task changes: its own columns, its tags (rows of
their own), its recurrence (a series it points at), and cascades that touch
rows no route handled directly.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlmodel import col, select

from app.models import (
    ActivityAction,
    ActivityEntityType,
    ActivityEntry,
    Deletion,
    Project,
    Series,
    Tag,
    Task,
    TaskPriority,
    TaskTag,
)

_ACTOR_KEY = "activity_actor_id"
_PENDING_KEY = "activity_pending"

# The task fields a "changed" entry reports. Completion, project and assignee
# have entries of their own.
_CHANGED_FIELDS = ("title", "description", "due_date", "priority", "tags", "recurrence")


def set_actor(session: Session, actor_id: uuid.UUID) -> None:
    """Attribute every change this session commits to `actor_id`."""
    session.info[_ACTOR_KEY] = actor_id


@dataclass(frozen=True)
class _TaskState:
    owner_id: uuid.UUID
    title: str
    description: str | None
    due_date: date | None
    priority: TaskPriority | None
    completed: bool
    project_id: uuid.UUID | None
    assignee_id: uuid.UUID | None
    deletion_id: uuid.UUID | None
    tags: tuple[str, ...]
    recurrence: dict[str, Any] | None


@dataclass
class _Pending:
    # Each task this transaction touched, with its state before it did — None
    # for a task the transaction created. Insertion order is the order changes
    # were first seen, which the entries keep.
    before: dict[uuid.UUID, _TaskState | None] = field(default_factory=dict)
    # Deletion events aimed at a task, in the order they were made.
    deletions: list[uuid.UUID] = field(default_factory=list)


@event.listens_for(Session, "before_flush")
def _collect(session: Session, _flush_context: Any, _instances: Any) -> None:
    with session.no_autoflush:
        touched: list[uuid.UUID] = []
        pending = session.info.get(_PENDING_KEY)

        created = [obj.id for obj in session.new if isinstance(obj, Task)]
        deletions = [
            obj.id
            for obj in session.new
            if isinstance(obj, Deletion) and obj.task_id is not None
        ]
        for obj in session.new | session.deleted:
            if isinstance(obj, TaskTag):
                touched.append(obj.task_id)
        for obj in session.dirty:
            if not session.is_modified(obj):
                continue
            if isinstance(obj, Task):
                touched.append(obj.id)
            elif isinstance(obj, Series):
                touched.extend(_open_occurrences(session, obj.id))

        if not (created or deletions or touched):
            return
        if pending is None:
            pending = session.info[_PENDING_KEY] = _Pending()

        for task_id in created:
            pending.before.setdefault(task_id, None)
        pending.deletions.extend(deletions)
        unseen = [task_id for task_id in touched if task_id not in pending.before]
        states = _load_states(session, unseen)
        for task_id in unseen:
            if task_id in states:
                pending.before[task_id] = states[task_id]


@event.listens_for(Session, "before_commit")
def _write(session: Session) -> None:
    if _PENDING_KEY not in session.info:
        return
    # Whatever is still waiting to be flushed is part of what gets logged.
    session.flush()
    pending: _Pending = session.info.pop(_PENDING_KEY)

    after = _load_states(session, list(pending.before))
    projects = _ProjectRefs(session)
    # Changes made outside a request, such as a script, have no one else to
    # attribute them to than the account they belong to.
    actor_id: uuid.UUID | None = session.info.get(_ACTOR_KEY)
    entries: list[ActivityEntry] = []

    for task_id, before in pending.before.items():
        state = after.get(task_id)
        # A task deleted in this transaction is logged once, by its deletion
        # event, rather than for each row the cascade took down.
        if state is None or state.deletion_id is not None:
            continue
        entries.extend(
            _task_entries(task_id, before, state, actor_id or state.owner_id, projects)
        )

    for deletion_id in pending.deletions:
        entries.append(_deletion_entry(session, deletion_id, actor_id, projects))

    session.add_all(entries)


@event.listens_for(Session, "after_transaction_end")
def _discard(session: Session, transaction: Any) -> None:
    # A transaction that ends without committing takes its changes with it,
    # and must not leave them to be logged by the next one.
    if transaction.parent is None:
        session.info.pop(_PENDING_KEY, None)


class _ProjectRefs:
    """
    A project as an entry names it: its id, and its name at the time of the
    change, so the entry still says where a task was after the project is
    renamed or gone.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._names: dict[uuid.UUID, str] = {}

    def __call__(self, project_id: uuid.UUID | None) -> dict[str, Any] | None:
        if project_id is None:
            return None
        if project_id not in self._names:
            self._names[project_id] = self._session.get_one(Project, project_id).name
        return {"id": project_id, "name": self._names[project_id]}


def _task_entries(
    task_id: uuid.UUID,
    before: _TaskState | None,
    after: _TaskState,
    actor_id: uuid.UUID,
    projects: _ProjectRefs,
) -> list[ActivityEntry]:
    def entry(action: ActivityAction, **details: Any) -> ActivityEntry:
        return ActivityEntry(
            owner_id=after.owner_id,
            actor_id=actor_id,
            action=action,
            entity_type=ActivityEntityType.TASK,
            entity_id=task_id,
            # Every entry names its task as it was titled at the time, so it
            # reads on its own whatever happens to the task afterwards.
            details=to_jsonable_python({"title": after.title, **details}),
        )

    if before is None:
        return [entry(ActivityAction.TASK_CREATED, task=_snapshot(after, projects))]

    entries = []
    changes = {
        name: {"from": getattr(before, name), "to": getattr(after, name)}
        for name in _CHANGED_FIELDS
        if getattr(before, name) != getattr(after, name)
    }
    if changes:
        entries.append(entry(ActivityAction.TASK_CHANGED, changes=changes))

    if before.project_id != after.project_id:
        entries.append(
            entry(
                ActivityAction.TASK_MOVED,
                from_project=projects(before.project_id),
                to_project=projects(after.project_id),
            )
        )

    if before.assignee_id != after.assignee_id:
        if after.assignee_id is None:
            entries.append(
                entry(
                    ActivityAction.TASK_UNASSIGNED,
                    previous_assignee_id=before.assignee_id,
                )
            )
        else:
            entries.append(
                entry(
                    ActivityAction.TASK_ASSIGNED,
                    assignee_id=after.assignee_id,
                    previous_assignee_id=before.assignee_id,
                )
            )

    if before.completed != after.completed:
        entries.append(
            entry(
                ActivityAction.TASK_COMPLETED
                if after.completed
                else ActivityAction.TASK_REOPENED
            )
        )

    return entries


def _deletion_entry(
    session: Session,
    deletion_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    projects: _ProjectRefs,
) -> ActivityEntry:
    deletion = session.get_one(Deletion, deletion_id)
    assert deletion.task_id is not None
    task = session.get_one(Task, deletion.task_id)
    went_down = session.execute(
        select(col(Task.id)).where(Task.deletion_id == deletion_id)
    ).all()
    return ActivityEntry(
        owner_id=deletion.owner_id,
        actor_id=actor_id or deletion.owner_id,
        action=ActivityAction.TASK_DELETED,
        entity_type=ActivityEntityType.TASK,
        entity_id=task.id,
        deletion_id=deletion.id,
        details=to_jsonable_python(
            {
                "title": task.title,
                "project": projects(task.project_id),
                "parent_id": task.parent_id,
                # What a restore of this event would bring back along with it.
                "subtask_count": len(went_down) - 1,
            }
        ),
    )


def _snapshot(state: _TaskState, projects: _ProjectRefs) -> dict[str, Any]:
    return {
        "title": state.title,
        "description": state.description,
        "due_date": state.due_date,
        "priority": state.priority,
        "completed": state.completed,
        "project": projects(state.project_id),
        "assignee_id": state.assignee_id,
        "tags": state.tags,
        "recurrence": state.recurrence,
    }


def _open_occurrences(session: Session, series_id: uuid.UUID) -> list[uuid.UUID]:
    rows = session.execute(
        select(col(Task.id)).where(
            Task.series_id == series_id,
            Task.completed == False,  # noqa: E712
            col(Task.deletion_id).is_(None),
        )
    ).all()
    return [row.id for row in rows]


def _load_states(
    session: Session, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, _TaskState]:
    """
    Tasks as the database holds them right now. Read with plain column
    selects, so the answer comes from the database and not from objects the
    session is still holding changes on.
    """
    if not task_ids:
        return {}

    # More columns than `select` has typed overloads for.
    columns: list[Any] = [
        col(Task.id),
        col(Task.owner_id),
        col(Task.title),
        col(Task.description),
        col(Task.due_date),
        col(Task.priority),
        col(Task.completed),
        col(Task.project_id),
        col(Task.assignee_id),
        col(Task.deletion_id),
        col(Series.frequency),
        col(Series.interval_days),
    ]
    rows = session.execute(
        select(*columns)
        .outerjoin(Series, col(Series.id) == Task.series_id)
        .where(col(Task.id).in_(task_ids))
    ).all()

    tags: dict[uuid.UUID, list[str]] = {task_id: [] for task_id in task_ids}
    for task_id, name in session.execute(
        select(col(TaskTag.task_id), col(Tag.name))
        .join(Tag, col(Tag.id) == TaskTag.tag_id)
        .where(col(TaskTag.task_id).in_(task_ids))
    ).all():
        tags[task_id].append(name)

    return {
        row.id: _TaskState(
            owner_id=row.owner_id,
            title=row.title,
            description=row.description,
            due_date=row.due_date,
            priority=row.priority,
            completed=row.completed,
            project_id=row.project_id,
            assignee_id=row.assignee_id,
            deletion_id=row.deletion_id,
            tags=tuple(sorted(tags[row.id], key=str.lower)),
            recurrence=(
                {"frequency": row.frequency, "interval_days": row.interval_days}
                if row.frequency is not None
                else None
            ),
        )
        for row in rows
    }
