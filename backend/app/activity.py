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
    Attachment,
    BotUser,
    Comment,
    Deletion,
    Project,
    Series,
    Tag,
    Task,
    TaskPriority,
    TaskStatus,
    TaskTag,
)

_ACTOR_KEY = "activity_actor"
_PENDING_KEY = "activity_pending"

# The task fields a "changed" entry reports. Completion, project and assignee
# have entries of their own.
_CHANGED_FIELDS = ("title", "description", "due_date", "priority", "tags", "recurrence")


@dataclass(frozen=True)
class _Actor:
    user_id: uuid.UUID | None = None
    bot_user_id: uuid.UUID | None = None


def set_actor(session: Session, user_id: uuid.UUID) -> None:
    """Attribute every change this session commits to the user `user_id`."""
    session.info[_ACTOR_KEY] = _Actor(user_id=user_id)


_BATCH_KEY = "activity_batch"


def set_batch(
    session: Session,
    action: ActivityAction,
    task_ids: list[uuid.UUID],
    details: dict[str, Any],
) -> None:
    """
    Log this transaction as one act over many tasks, rather than as each task
    it touched.

    The user pressed one control over a selection; a log that reported the
    tasks one by one would be a record of how the request was implemented
    rather than of what they did (semaputnik/taskly#66, story 27).
    """
    session.info[_BATCH_KEY] = (action, set(task_ids), details)


_TAG_MERGE_KEY = "activity_tag_merge"


def set_tag_merge(
    session: Session,
    *,
    target: Tag,
    source_ids: list[uuid.UUID],
    sources: list[str],
    task_count: int,
) -> None:
    """
    Log this transaction as one merge of `sources` into `target`, rather than
    as every task whose tags it rewrote and every source tag it removed: the
    user made one decision, and the log records that (FR-01.27).
    """
    session.info[_TAG_MERGE_KEY] = _TagMerge(
        entry=_entry(
            target.owner_id,
            ActivityAction.TAG_MERGED,
            ActivityEntityType.TAG,
            target.id,
            name=target.name,
            sources=sources,
            task_count=task_count,
        ),
        source_ids=set(source_ids),
    )


@dataclass(frozen=True)
class _TagMerge:
    entry: ActivityEntry
    source_ids: set[uuid.UUID]


def set_bot_actor(session: Session, bot_user_id: uuid.UUID) -> None:
    """
    Attribute every change this session commits to the bot user
    `bot_user_id`, and so never to its owner (FR-10.2).
    """
    session.info[_ACTOR_KEY] = _Actor(bot_user_id=bot_user_id)


@dataclass(frozen=True)
class _TaskState:
    owner_id: uuid.UUID
    title: str
    description: str | None
    due_date: date | None
    priority: TaskPriority | None
    status: TaskStatus
    project_id: uuid.UUID | None
    assignee_id: uuid.UUID | None
    assignee_bot_user_id: uuid.UUID | None
    deletion_id: uuid.UUID | None
    tags: tuple[str, ...]
    recurrence: dict[str, Any] | None


@dataclass(frozen=True)
class _ProjectState:
    owner_id: uuid.UUID
    name: str
    description: str | None
    deletion_id: uuid.UUID | None


@dataclass
class _Pending:
    # Each task this transaction touched, with its state before it did — None
    # for a task the transaction created. Insertion order is the order changes
    # were first seen, which the entries keep.
    before: dict[uuid.UUID, _TaskState | None] = field(default_factory=dict)
    # Deletion events aimed at a task, in the order they were made.
    deletions: list[uuid.UUID] = field(default_factory=list)
    # The same for projects: state before, or None for one created here.
    projects: dict[uuid.UUID, _ProjectState | None] = field(default_factory=dict)
    project_deletions: list[uuid.UUID] = field(default_factory=list)
    # Each comment touched, with its body before — None for a new one.
    comments: dict[uuid.UUID, str | None] = field(default_factory=dict)
    attachments_added: list[uuid.UUID] = field(default_factory=list)
    tags_created: list[uuid.UUID] = field(default_factory=list)
    # Each tag renamed, with its name before.
    tag_names: dict[uuid.UUID, str] = field(default_factory=dict)
    # Rows removed outright are gone by commit, so what an entry needs to say
    # about them is taken while they are still in the session.
    removed: list[ActivityEntry] = field(default_factory=list)


@event.listens_for(Session, "before_flush")
def _collect(session: Session, _flush_context: Any, _instances: Any) -> None:
    with session.no_autoflush:
        pending = session.info.get(_PENDING_KEY) or _Pending()
        found = False

        touched: list[uuid.UUID] = []
        touched_projects: list[uuid.UUID] = []
        touched_comments: list[uuid.UUID] = []
        touched_tags: list[uuid.UUID] = []

        for obj in session.new:
            found = found or isinstance(
                obj, Task | Deletion | TaskTag | Project | Comment | Attachment | Tag
            )
            if isinstance(obj, Task):
                pending.before.setdefault(obj.id, None)
            elif isinstance(obj, Deletion) and obj.project_id is not None:
                pending.project_deletions.append(obj.id)
            elif isinstance(obj, Deletion):
                # A task's deletion, or a batch's — which names no single task
                # and is logged by what it took down.
                pending.deletions.append(obj.id)
            elif isinstance(obj, TaskTag):
                touched.append(obj.task_id)
            # The Inbox comes with the account rather than being made by
            # anyone, so it is not a change the user made.
            elif isinstance(obj, Project) and not obj.is_inbox:
                pending.projects.setdefault(obj.id, None)
            elif isinstance(obj, Comment):
                pending.comments.setdefault(obj.id, None)
            elif isinstance(obj, Attachment):
                pending.attachments_added.append(obj.id)
            elif isinstance(obj, Tag):
                pending.tags_created.append(obj.id)

        for obj in session.deleted:
            if isinstance(obj, TaskTag):
                found = True
                touched.append(obj.task_id)
            elif isinstance(obj, Comment):
                found = True
                pending.removed.append(_comment_deleted_entry(session, obj))
            elif isinstance(obj, Attachment):
                found = True
                pending.removed.append(_attachment_deleted_entry(session, obj))
            elif isinstance(obj, Tag):
                found = True
                pending.removed.append(_tag_deleted_entry(session, obj))

        for obj in session.dirty:
            if not session.is_modified(obj):
                continue
            if isinstance(obj, Task):
                touched.append(obj.id)
            elif isinstance(obj, Series):
                touched.extend(_open_occurrences(session, obj.id))
            elif isinstance(obj, Project):
                touched_projects.append(obj.id)
            elif isinstance(obj, Comment):
                touched_comments.append(obj.id)
            elif isinstance(obj, Tag):
                touched_tags.append(obj.id)

        if not (
            found or touched or touched_projects or touched_comments or touched_tags
        ):
            return
        session.info[_PENDING_KEY] = pending

        unseen = [task_id for task_id in touched if task_id not in pending.before]
        states = _load_states(session, unseen)
        for task_id in unseen:
            if task_id in states:
                pending.before[task_id] = states[task_id]

        unseen = [pid for pid in touched_projects if pid not in pending.projects]
        project_states = _load_project_states(session, unseen)
        for project_id in unseen:
            if project_id in project_states:
                pending.projects[project_id] = project_states[project_id]

        unseen = [cid for cid in touched_comments if cid not in pending.comments]
        bodies = _load_comment_bodies(session, unseen)
        for comment_id in unseen:
            if comment_id in bodies:
                pending.comments[comment_id] = bodies[comment_id]

        unseen = [tid for tid in touched_tags if tid not in pending.tag_names]
        names = _load_tag_names(session, unseen)
        for tag_id in unseen:
            if tag_id in names:
                pending.tag_names[tag_id] = names[tag_id]


@event.listens_for(Session, "before_commit")
def _write(session: Session) -> None:
    # Commit flushes only after this hook has run, too late for what it writes
    # to be seen here, so anything still waiting is flushed first: a change
    # committed without a flush of its own is logged like any other.
    if session.new or session.dirty or session.deleted:
        session.flush()
    batch: tuple[ActivityAction, set[uuid.UUID], dict[str, Any]] | None = (
        session.info.pop(_BATCH_KEY, None)
    )
    merge: _TagMerge | None = session.info.pop(_TAG_MERGE_KEY, None)
    if _PENDING_KEY not in session.info:
        return
    pending: _Pending = session.info.pop(_PENDING_KEY)

    after = _load_states(session, list(pending.before))
    refs = _Refs(session)
    # Tags first: a tag typed onto a task comes into being before the task
    # carries it, and the log reads in that order.
    entries: list[ActivityEntry] = _tag_entries(session, pending)
    # Deletion events this transaction brought rows back from, each with how
    # many of its rows came back.
    restored: dict[uuid.UUID, int] = {}

    batched: list[uuid.UUID] = []

    for task_id, before in pending.before.items():
        state = after.get(task_id)
        # A task deleted in this transaction is logged once, by its deletion
        # event, rather than for each row the cascade took down.
        if state is None or state.deletion_id is not None:
            continue
        # Restoring is logged the same way: once for the event, not per row.
        if before is not None and before.deletion_id is not None:
            restored[before.deletion_id] = restored.get(before.deletion_id, 0) + 1
        if merge is not None:
            # A merge rewrites tags and nothing else; its entry says so once.
            continue
        if batch is not None:
            # The subtasks a completion swept along are part of the same act,
            # and are not counted as tasks the reader picked.
            if task_id in batch[1]:
                batched.append(task_id)
            continue
        entries.extend(_task_entries(task_id, before, state, refs))

    if batch is not None and batched:
        action, _selected, details = batch
        entries.append(
            _entry(
                after[batched[0]].owner_id,
                action,
                ActivityEntityType.TASK,
                batched[0],
                task_count=len(batched),
                task_ids=[str(task_id) for task_id in batched],
                **details,
            )
        )

    for deletion_id in pending.deletions:
        entries.append(_deletion_entry(session, deletion_id, refs))

    for deletion_id, count in restored.items():
        # A project's tasks coming back are part of the project's restore,
        # which is logged with the project below. A batch's are not: the batch
        # is the act, and its undo is an act of its own.
        if session.get_one(Deletion, deletion_id).project_id is None:
            entries.append(_restore_entry(session, deletion_id, count, refs))

    entries.extend(_project_entries(session, pending, restored))
    entries.extend(_comment_entries(session, pending))
    for attachment_id in pending.attachments_added:
        attachment = session.get(Attachment, attachment_id)
        if attachment is not None:
            entries.append(_attachment_added_entry(session, attachment))
    if merge is None:
        entries.extend(pending.removed)
    else:
        entries.extend(
            entry
            for entry in pending.removed
            if entry.entity_id not in merge.source_ids
        )
        entries.append(merge.entry)

    actor: _Actor | None = session.info.get(_ACTOR_KEY)
    for entry in entries:
        if actor is None:
            # Changes made outside a request, such as a script, have no one
            # else to attribute them to than the account they belong to.
            entry.actor_id = entry.owner_id
        else:
            entry.actor_id = actor.user_id
            entry.actor_bot_user_id = actor.bot_user_id
    session.add_all(entries)


@event.listens_for(Session, "after_transaction_end")
def _discard(session: Session, transaction: Any) -> None:
    # A transaction that ends without committing takes its changes with it,
    # and must not leave them to be logged by the next one.
    if transaction.parent is None:
        session.info.pop(_PENDING_KEY, None)
        session.info.pop(_BATCH_KEY, None)
        session.info.pop(_TAG_MERGE_KEY, None)


class _Refs:
    """
    Other things as an entry names them, with their names at the time of the
    change, so the entry still reads after they are renamed or gone.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._project_names: dict[uuid.UUID, str] = {}
        self._bot_user_names: dict[uuid.UUID, str] = {}

    def project(self, project_id: uuid.UUID | None) -> dict[str, Any] | None:
        """A project: its id and name."""
        if project_id is None:
            return None
        if project_id not in self._project_names:
            project = self._session.get_one(Project, project_id)
            self._project_names[project_id] = project.name
        return {"id": project_id, "name": self._project_names[project_id]}

    def assignee(self, state: _TaskState) -> dict[str, Any] | None:
        """
        Who a task is assigned to: the user, or a bot user with its name — a
        bot user can be renamed or deleted later, the user is always "you".
        """
        if state.assignee_id is not None:
            return {"type": "user", "id": state.assignee_id}
        bot_user_id = state.assignee_bot_user_id
        if bot_user_id is None:
            return None
        if bot_user_id not in self._bot_user_names:
            bot_user = self._session.get_one(BotUser, bot_user_id)
            self._bot_user_names[bot_user_id] = bot_user.name
        return {
            "type": "bot_user",
            "id": bot_user_id,
            "name": self._bot_user_names[bot_user_id],
        }


def _task_entries(
    task_id: uuid.UUID,
    before: _TaskState | None,
    after: _TaskState,
    refs: _Refs,
) -> list[ActivityEntry]:
    def entry(action: ActivityAction, **details: Any) -> ActivityEntry:
        return ActivityEntry(
            owner_id=after.owner_id,
            action=action,
            entity_type=ActivityEntityType.TASK,
            entity_id=task_id,
            # Every entry names its task as it was titled at the time, so it
            # reads on its own whatever happens to the task afterwards.
            details=to_jsonable_python({"title": after.title, **details}),
        )

    if before is None:
        return [entry(ActivityAction.TASK_CREATED, task=_snapshot(after, refs))]

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
                from_project=refs.project(before.project_id),
                to_project=refs.project(after.project_id),
            )
        )

    previous_assignee = refs.assignee(before)
    assignee = refs.assignee(after)
    if previous_assignee != assignee:
        # `assignee_id` and `previous_assignee_id` stay as entries have always
        # had them; `assignee` and `previous_assignee` say who that is.
        if assignee is None:
            entries.append(
                entry(
                    ActivityAction.TASK_UNASSIGNED,
                    previous_assignee_id=_assignee_id(before),
                    previous_assignee=previous_assignee,
                )
            )
        else:
            entries.append(
                entry(
                    ActivityAction.TASK_ASSIGNED,
                    assignee_id=_assignee_id(after),
                    assignee=assignee,
                    previous_assignee_id=_assignee_id(before),
                    previous_assignee=previous_assignee,
                )
            )

    if before.status != after.status:
        # To or out of done keeps the entries the log has always had; only a
        # move between open statuses is new, and it names both ends.
        if after.status is TaskStatus.DONE:
            entries.append(entry(ActivityAction.TASK_COMPLETED))
        elif before.status is TaskStatus.DONE:
            entries.append(entry(ActivityAction.TASK_REOPENED, to=after.status))
        else:
            entries.append(
                entry(
                    ActivityAction.TASK_STATUS_CHANGED,
                    **{"from": before.status, "to": after.status},
                )
            )

    return entries


def _deletion_entry(
    session: Session,
    deletion_id: uuid.UUID,
    refs: _Refs,
) -> ActivityEntry:
    deletion = session.get_one(Deletion, deletion_id)
    went_down = session.execute(
        select(col(Task.id)).where(Task.deletion_id == deletion_id)
    ).all()
    if deletion.task_id is None:
        # A batch names no single task: it is the selection that went down,
        # and the count is what the entry has to say (story 27).
        return ActivityEntry(
            owner_id=deletion.owner_id,
            action=ActivityAction.TASK_DELETED,
            entity_type=ActivityEntityType.TASK,
            # An entry points at something; for a batch the first row it took
            # is as good a handle as any, and the restore goes by the event.
            entity_id=went_down[0][0],
            deletion_id=deletion.id,
            details=to_jsonable_python({"task_count": len(went_down)}),
        )
    task = session.get_one(Task, deletion.task_id)
    return ActivityEntry(
        owner_id=deletion.owner_id,
        action=ActivityAction.TASK_DELETED,
        entity_type=ActivityEntityType.TASK,
        entity_id=task.id,
        deletion_id=deletion.id,
        details=to_jsonable_python(
            {
                "title": task.title,
                "project": refs.project(task.project_id),
                "parent_id": task.parent_id,
                # What a restore of this event would bring back along with it.
                "subtask_count": len(went_down) - 1,
            }
        ),
    )


def _restore_entry(
    session: Session,
    deletion_id: uuid.UUID,
    count: int,
    refs: _Refs,
) -> ActivityEntry:
    deletion = session.get_one(Deletion, deletion_id)
    if deletion.task_id is None:
        # A batch coming back: what was restored is the selection that went
        # down, said as the count it is.
        return ActivityEntry(
            owner_id=deletion.owner_id,
            action=ActivityAction.TASK_RESTORED,
            entity_type=ActivityEntityType.TASK,
            entity_id=deletion_id,
            deletion_id=deletion_id,
            details=to_jsonable_python({"task_count": count}),
        )
    task = session.get_one(Task, deletion.task_id)
    return ActivityEntry(
        owner_id=deletion.owner_id,
        action=ActivityAction.TASK_RESTORED,
        entity_type=ActivityEntityType.TASK,
        entity_id=task.id,
        # The event it undid, so the log reads which deletion came back.
        deletion_id=deletion.id,
        details=to_jsonable_python(
            {
                "title": task.title,
                "project": refs.project(task.project_id),
                "parent_id": task.parent_id,
                "subtask_count": count - 1,
            }
        ),
    )


def _assignee_id(state: _TaskState) -> uuid.UUID | None:
    return state.assignee_id or state.assignee_bot_user_id


def _snapshot(state: _TaskState, refs: _Refs) -> dict[str, Any]:
    return {
        "title": state.title,
        "description": state.description,
        "due_date": state.due_date,
        "priority": state.priority,
        "status": state.status,
        "project": refs.project(state.project_id),
        "assignee_id": _assignee_id(state),
        "assignee": refs.assignee(state),
        "tags": state.tags,
        "recurrence": state.recurrence,
    }


def _open_occurrences(session: Session, series_id: uuid.UUID) -> list[uuid.UUID]:
    rows = session.execute(
        select(col(Task.id)).where(
            Task.series_id == series_id,
            col(Task.status) != TaskStatus.DONE,
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
        col(Task.status),
        col(Task.project_id),
        col(Task.assignee_id),
        col(Task.assignee_bot_user_id),
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
            status=row.status,
            project_id=row.project_id,
            assignee_id=row.assignee_id,
            assignee_bot_user_id=row.assignee_bot_user_id,
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


def _task_ref(session: Session, task_id: uuid.UUID) -> dict[str, Any]:
    """A task as a comment or attachment entry names it."""
    task = session.get_one(Task, task_id)
    return {"id": task.id, "title": task.title}


def _entry(
    owner_id: uuid.UUID,
    action: ActivityAction,
    entity_type: ActivityEntityType,
    entity_id: uuid.UUID,
    **details: Any,
) -> ActivityEntry:
    return ActivityEntry(
        owner_id=owner_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=to_jsonable_python(details),
    )


def _project_entries(
    session: Session, pending: _Pending, restored: dict[uuid.UUID, int]
) -> list[ActivityEntry]:
    """
    `restored` counts the tasks this transaction brought back, by the deletion
    event they came back from, so a project's restore can say how many of its
    tasks came with it.
    """
    entries = []
    after = _load_project_states(session, list(pending.projects))
    for project_id, before in pending.projects.items():
        state = after.get(project_id)
        # Deleting is logged by its deletion event below.
        if state is None or state.deletion_id is not None:
            continue
        if before is not None and before.deletion_id is not None:
            entry = _entry(
                state.owner_id,
                ActivityAction.PROJECT_RESTORED,
                ActivityEntityType.PROJECT,
                project_id,
                name=state.name,
                task_count=restored.get(before.deletion_id, 0),
            )
            # The event it undid, so the log reads which deletion came back.
            entry.deletion_id = before.deletion_id
            entries.append(entry)
            continue
        if before is None:
            entries.append(
                _entry(
                    state.owner_id,
                    ActivityAction.PROJECT_CREATED,
                    ActivityEntityType.PROJECT,
                    project_id,
                    name=state.name,
                    description=state.description,
                )
            )
            continue
        # Archiving is deliberately not a change the log records (FR-05.10),
        # so only the fields a user edits are compared.
        changes = {
            name: {"from": getattr(before, name), "to": getattr(state, name)}
            for name in ("name", "description")
            if getattr(before, name) != getattr(state, name)
        }
        if changes:
            entries.append(
                _entry(
                    state.owner_id,
                    ActivityAction.PROJECT_CHANGED,
                    ActivityEntityType.PROJECT,
                    project_id,
                    name=state.name,
                    changes=changes,
                )
            )

    for deletion_id in pending.project_deletions:
        deletion = session.get_one(Deletion, deletion_id)
        assert deletion.project_id is not None
        project = session.get_one(Project, deletion.project_id)
        went_down = session.execute(
            select(col(Task.id)).where(Task.deletion_id == deletion_id)
        ).all()
        entry = _entry(
            deletion.owner_id,
            ActivityAction.PROJECT_DELETED,
            ActivityEntityType.PROJECT,
            project.id,
            name=project.name,
            # What a restore of this event would bring back along with it.
            task_count=len(went_down),
        )
        entry.deletion_id = deletion.id
        entries.append(entry)
    return entries


def _comment_entries(session: Session, pending: _Pending) -> list[ActivityEntry]:
    entries = []
    bodies = _load_comment_bodies(session, list(pending.comments))
    for comment_id, before in pending.comments.items():
        comment = session.get(Comment, comment_id)
        if comment is None or comment_id not in bodies:
            continue
        if before is None:
            entries.append(
                _entry(
                    comment.owner_id,
                    ActivityAction.COMMENT_ADDED,
                    ActivityEntityType.COMMENT,
                    comment_id,
                    task=_task_ref(session, comment.task_id),
                    body=bodies[comment_id],
                )
            )
        elif before != bodies[comment_id]:
            entries.append(
                _entry(
                    comment.owner_id,
                    ActivityAction.COMMENT_EDITED,
                    ActivityEntityType.COMMENT,
                    comment_id,
                    task=_task_ref(session, comment.task_id),
                    changes={"body": {"from": before, "to": bodies[comment_id]}},
                )
            )
    return entries


def _comment_deleted_entry(session: Session, comment: Comment) -> ActivityEntry:
    return _entry(
        comment.owner_id,
        ActivityAction.COMMENT_DELETED,
        ActivityEntityType.COMMENT,
        comment.id,
        task=_task_ref(session, comment.task_id),
        # A deleted comment is gone for good, so its words are kept here.
        body=comment.body,
    )


def _attachment_added_entry(session: Session, attachment: Attachment) -> ActivityEntry:
    return _entry(
        attachment.owner_id,
        ActivityAction.ATTACHMENT_ADDED,
        ActivityEntityType.ATTACHMENT,
        attachment.id,
        task=_task_ref(session, attachment.task_id),
        filename=attachment.filename,
        content_type=attachment.content_type,
        size=attachment.size,
    )


def _attachment_deleted_entry(
    session: Session, attachment: Attachment
) -> ActivityEntry:
    entry = _attachment_added_entry(session, attachment)
    entry.action = ActivityAction.ATTACHMENT_DELETED
    return entry


def _load_project_states(
    session: Session, project_ids: list[uuid.UUID]
) -> dict[uuid.UUID, _ProjectState]:
    if not project_ids:
        return {}
    rows = session.execute(
        select(
            col(Project.id),
            col(Project.owner_id),
            col(Project.name),
            col(Project.description),
        )
        .add_columns(col(Project.deletion_id))
        .where(col(Project.id).in_(project_ids))
    ).all()
    return {
        row.id: _ProjectState(
            owner_id=row.owner_id,
            name=row.name,
            description=row.description,
            deletion_id=row.deletion_id,
        )
        for row in rows
    }


def _load_comment_bodies(
    session: Session, comment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not comment_ids:
        return {}
    rows = session.execute(
        select(col(Comment.id), col(Comment.body)).where(
            col(Comment.id).in_(comment_ids)
        )
    ).all()
    return {row.id: row.body for row in rows}


def _tag_entries(session: Session, pending: _Pending) -> list[ActivityEntry]:
    entries = []
    for tag_id in pending.tags_created:
        tag = session.get(Tag, tag_id)
        if tag is not None:
            entries.append(
                _entry(
                    tag.owner_id,
                    ActivityAction.TAG_CREATED,
                    ActivityEntityType.TAG,
                    tag_id,
                    name=tag.name,
                )
            )
    after = _load_tag_names(session, list(pending.tag_names))
    for tag_id, before in pending.tag_names.items():
        # A tag created in this transaction is logged once, as created.
        if tag_id in pending.tags_created or tag_id not in after:
            continue
        if after[tag_id] != before:
            tag = session.get_one(Tag, tag_id)
            entries.append(
                _entry(
                    tag.owner_id,
                    ActivityAction.TAG_RENAMED,
                    ActivityEntityType.TAG,
                    tag_id,
                    name=after[tag_id],
                    changes={"name": {"from": before, "to": after[tag_id]}},
                )
            )
    return entries


def _tag_deleted_entry(session: Session, tag: Tag) -> ActivityEntry:
    """
    A tag deletion, written while the tag's links are still there to count:
    the database takes them away with the tag.
    """
    rows = session.execute(
        select(col(TaskTag.task_id)).where(
            TaskTag.tag_id == tag.id,
            TaskTag.task_id == Task.id,
            col(Task.deletion_id).is_(None),
        )
    ).all()
    return _entry(
        tag.owner_id,
        ActivityAction.TAG_DELETED,
        ActivityEntityType.TAG,
        tag.id,
        # A deleted tag is gone for good, so its name is kept here.
        name=tag.name,
        task_count=len(rows),
    )


def _load_tag_names(session: Session, tag_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not tag_ids:
        return {}
    rows = session.execute(
        select(col(Tag.id), col(Tag.name)).where(col(Tag.id).in_(tag_ids))
    ).all()
    return {row.id: row.name for row in rows}
