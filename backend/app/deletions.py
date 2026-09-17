"""
Deletion events: one act of deleting and everything it took down, from the
delete to the restore (FR-01.8, FR-05.8, FR-10.4).

An event comes in three kinds — a task with its subtree, a project with its
tasks, or a batch of tasks — and the kinds stay in here. Deleting marks
exactly the rows the act takes down with the event. Whether an event can be
restored now is one answer, used both for the log's `restorable` flag and by
the restore itself, so the two cannot disagree. Restoring brings back exactly
the rows still marked by the event, which leaves anything deleted on its own
beforehand deleted (FR-01.10).
"""

import uuid
from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import orm
from sqlmodel import Session, col, select

from app import crud
from app.models import Deletion, Project, Task, TaskStatus


class DeletionKind(StrEnum):
    TASK = "task"
    PROJECT = "project"
    BATCH = "batch"


def kind_of(deletion: Deletion) -> DeletionKind:
    """
    What an event deleted. A batch names no single task — the user pointed at
    a selection — so the rows it marks are the whole of what it took down.
    """
    if deletion.project_id is not None:
        return DeletionKind.PROJECT
    if deletion.task_id is not None:
        return DeletionKind.TASK
    return DeletionKind.BATCH


# Deleting


def _mark(session: Session, deletion: Deletion, task_ids: Any) -> None:
    for task in session.exec(select(Task).where(col(Task.id).in_(task_ids))):
        task.deletion_id = deletion.id
        session.add(task)


def _begin(session: Session, deletion: Deletion) -> Deletion:
    session.add(deletion)
    # The event row has to exist before anything can point at it.
    session.flush()
    return deletion


def delete_task(session: Session, task: Task) -> uuid.UUID:
    """Delete a task and its subtree as one event (FR-01.8, FR-01.11)."""
    deletion = _begin(session, Deletion(owner_id=task.owner_id, task_id=task.id))
    _mark(session, deletion, crud.subtree_ids(task.id))
    task.deletion_id = deletion.id
    session.add(task)
    session.commit()
    return deletion.id


def delete_tasks(session: Session, tasks: Sequence[Task]) -> uuid.UUID:
    """
    Delete several tasks and their subtrees as one event, so that one act is
    one thing to undo (FR-10.4).
    """
    deletion = _begin(session, Deletion(owner_id=tasks[0].owner_id))
    for task in tasks:
        _mark(session, deletion, crud.subtree_ids(task.id))
        task.deletion_id = deletion.id
        session.add(task)
    session.commit()
    return deletion.id


def delete_project(session: Session, project: Project) -> uuid.UUID:
    """Delete a project and every task in it as one event (FR-05.8, FR-05.9)."""
    deletion = _begin(
        session, Deletion(owner_id=project.owner_id, project_id=project.id)
    )
    _mark(session, deletion, crud.project_task_ids(project.id))
    project.deletion_id = deletion.id
    session.add(project)
    session.commit()
    return deletion.id


def marked_task_ids(session: orm.Session, deletion_id: uuid.UUID) -> set[uuid.UUID]:
    """
    The tasks the event took down that are still deleted by it. Takes any
    session, so the activity log can ask while it writes its entries.
    """
    statement = select(col(Task.id)).where(Task.deletion_id == deletion_id)
    return set(session.execute(statement).scalars().all())


# Restoring


class RestoreRefusal(StrEnum):
    """Why an event cannot be restored now."""

    #: Nothing is left to bring back: the event was restored.
    ALREADY_RESTORED = "already_restored"
    #: What it deleted was restored and then deleted again, by a later event.
    DELETED_AGAIN = "deleted_again"
    #: A task would come back under a parent that is still deleted.
    PARENT_DELETED = "parent_deleted"
    #: A task would come back into a project that is deleted.
    PROJECT_DELETED = "project_deleted"
    #: A task would come back into an archived project, which is read-only.
    PROJECT_ARCHIVED = "project_archived"
    #: A series would be left with two open occurrences (FR-01.16).
    SERIES_HAS_OPEN_OCCURRENCE = "series_has_open_occurrence"


@dataclass(frozen=True)
class Restorability:
    """Whether an event can be restored now, and if not, why."""

    kind: DeletionKind
    refusal: RestoreRefusal | None = None
    #: The task's title or the project's name the refusal is about.
    subject: str | None = None
    #: The deleted parent's title, for PARENT_DELETED.
    parent: str | None = None
    #: The project in the way, for PROJECT_DELETED and PROJECT_ARCHIVED.
    project: Project | None = None

    @property
    def restorable(self) -> bool:
        """Whether the event still has something to bring back."""
        return self.refusal not in (
            RestoreRefusal.ALREADY_RESTORED,
            RestoreRefusal.DELETED_AGAIN,
        )


def _by_id[T: Task | Project](
    session: Session, model: type[T], ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, T]:
    if not ids:
        return {}
    rows = session.exec(select(model).where(col(model.id).in_(set(ids)))).all()
    return {row.id: row for row in rows}


def _target[T: Task | Project](rows: dict[uuid.UUID, T], row_id: uuid.UUID | None) -> T:
    """The row an event names, which the event's kind says it has."""
    assert row_id is not None
    return rows[row_id]


def restorability(
    session: Session, owner_id: uuid.UUID, deletion_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, Restorability]:
    """
    Whether each of the owner's events can be restored now, keyed by event id,
    in a fixed number of queries however many events are asked about.
    """
    if not deletion_ids:
        return {}
    events = session.exec(
        select(Deletion).where(
            col(Deletion.id).in_(set(deletion_ids)), Deletion.owner_id == owner_id
        )
    ).all()
    marked: dict[uuid.UUID, list[Task]] = defaultdict(list)
    for task in session.exec(
        select(Task)
        .where(col(Task.deletion_id).in_([event.id for event in events]))
        .order_by(col(Task.created_at), col(Task.id))
    ).all():
        assert task.deletion_id is not None
        marked[task.deletion_id].append(task)
    targets = _by_id(
        session, Task, [e.task_id for e in events if e.task_id is not None]
    )
    projects = _by_id(
        session, Project, [e.project_id for e in events if e.project_id is not None]
    )

    # The tasks whose surroundings decide a task or batch restore: the task an
    # event named, or each task of a batch whose parent the batch did not take.
    checked: dict[uuid.UUID, list[Task]] = {}
    for deletion in events:
        rows = marked[deletion.id]
        if kind_of(deletion) is DeletionKind.TASK and rows:
            checked[deletion.id] = [_target(targets, deletion.task_id)]
        elif kind_of(deletion) is DeletionKind.BATCH:
            taken = {task.id for task in rows}
            checked[deletion.id] = [t for t in rows if t.parent_id not in taken]
    to_check = [task for tasks in checked.values() for task in tasks]
    parents = _by_id(
        session, Task, [t.parent_id for t in to_check if t.parent_id is not None]
    )
    # The tasks are deleted, so the walk up to their project goes through
    # deleted tasks too.
    project_of = crud.get_task_project_ids(
        session=session,
        owner_id=owner_id,
        task_ids=[task.id for task in to_check],
        including_deleted=True,
    )
    projects.update(_by_id(session, Project, set(project_of.values()) - set(projects)))
    open_series = _open_series(session, marked.values())

    def reopens_a_series(rows: Sequence[Task]) -> bool:
        return any(
            task.series_id in open_series
            for task in rows
            if task.status is not TaskStatus.DONE
        )

    verdicts: dict[uuid.UUID, Restorability] = {}
    for deletion in events:
        kind = kind_of(deletion)
        rows = marked[deletion.id]
        if kind is DeletionKind.PROJECT:
            project = _target(projects, deletion.project_id)
            verdicts[deletion.id] = _project_verdict(
                deletion, project, reopens_a_series(rows)
            )
            continue
        if not rows:
            gone = (
                kind is DeletionKind.TASK
                and _target(targets, deletion.task_id).deletion_id is not None
            )
            verdicts[deletion.id] = Restorability(
                kind,
                RestoreRefusal.DELETED_AGAIN
                if gone
                else RestoreRefusal.ALREADY_RESTORED,
            )
            continue
        verdict = Restorability(kind)
        for task in checked[deletion.id]:
            refused = _task_verdict(
                kind,
                task,
                parents.get(task.parent_id) if task.parent_id else None,
                projects[project_of[task.id]],
                reopens_a_series(rows),
            )
            if refused.refusal is not None:
                verdict = refused
                break
        verdicts[deletion.id] = verdict
    return verdicts


def _open_series(
    session: Session, marked: Collection[Sequence[Task]]
) -> set[uuid.UUID]:
    """
    The series among the marked open tasks that already have an open
    occurrence outside any deletion.
    """
    series_ids = {
        task.series_id
        for rows in marked
        for task in rows
        if task.series_id is not None and task.status is not TaskStatus.DONE
    }
    if not series_ids:
        return set()
    return {
        series_id
        for series_id in session.exec(
            select(Task.series_id)
            .where(
                col(Task.series_id).in_(series_ids),
                crud.is_open(Task),
                crud.not_deleted(Task),
            )
            .distinct()
        ).all()
        if series_id is not None
    }


def _project_verdict(
    deletion: Deletion, project: Project, reopens_a_series: bool
) -> Restorability:
    """
    A project comes back archived if it was archived when deleted: the two
    states are independent (FR-05.10), so that is no reason to refuse.
    """
    kind = DeletionKind.PROJECT
    if project.deletion_id is None:
        return Restorability(kind, RestoreRefusal.ALREADY_RESTORED)
    if project.deletion_id != deletion.id:
        return Restorability(kind, RestoreRefusal.DELETED_AGAIN)
    if reopens_a_series:
        # Refused as a whole: bringing the project back without one of its
        # tasks would be a restore nobody asked for.
        return Restorability(
            kind, RestoreRefusal.SERIES_HAS_OPEN_OCCURRENCE, subject=project.name
        )
    return Restorability(kind)


def _task_verdict(
    kind: DeletionKind,
    task: Task,
    parent: Task | None,
    project: Project,
    reopens_a_series: bool,
) -> Restorability:
    """Refuse a task that has nowhere to come back to."""
    if parent is not None and parent.deletion_id is not None:
        return Restorability(
            kind,
            RestoreRefusal.PARENT_DELETED,
            subject=task.title,
            parent=parent.title,
        )
    if project.deletion_id is not None:
        return Restorability(
            kind, RestoreRefusal.PROJECT_DELETED, subject=task.title, project=project
        )
    # Restoring writes into the project, so an archived one refuses it the
    # same way it refuses any other change.
    if project.is_archived:
        return Restorability(
            kind, RestoreRefusal.PROJECT_ARCHIVED, subject=task.title, project=project
        )
    if reopens_a_series:
        return Restorability(
            kind, RestoreRefusal.SERIES_HAS_OPEN_OCCURRENCE, subject=task.title
        )
    return Restorability(kind)


def restore(
    session: Session, owner_id: uuid.UUID, deletion_id: uuid.UUID
) -> Restorability:
    """
    Bring back the rows of one of the owner's events, if it can be restored
    now; either way, say whether it could.

    Clearing the marker is the whole restore, for a task and its subtasks and
    for a project and its tasks alike: nothing is re-created, so each row comes
    back as itself, with its comments, attachments, tags and history.
    Archiving is a separate state and is left as it was.
    """
    verdict = restorability(session, owner_id, [deletion_id])[deletion_id]
    if verdict.refusal is not None:
        return verdict
    deletion = session.get_one(Deletion, deletion_id)
    for task in session.exec(select(Task).where(Task.deletion_id == deletion_id)):
        task.deletion_id = None
        session.add(task)
    if deletion.project_id is not None:
        project = session.get_one(Project, deletion.project_id)
        project.deletion_id = None
        session.add(project)
    session.commit()
    return verdict
