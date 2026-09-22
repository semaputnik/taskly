"""
The deletion event module: deleting, whether an event can be restored now,
and restoring it — for a task, a project and a batch.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app import crud, deletions
from app.deletions import DeletionKind, RestoreRefusal
from app.models import (
    Deletion,
    Project,
    ProjectCreate,
    Recurrence,
    RecurrenceFrequency,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    User,
    UserCreate,
)
from tests.utils.utils import random_email, random_lower_string


@pytest.fixture
def owner(db: Session) -> User:
    return crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )


def _project(db: Session, owner: User, name: str = "Home") -> Project:
    return crud.create_project(
        session=db, project_create=ProjectCreate(name=name), owner_id=owner.id
    )


def _task(
    db: Session,
    owner: User,
    *,
    project: Project | None = None,
    parent: Task | None = None,
    title: str = "T",
    **fields: Any,
) -> Task:
    return crud.create_task(
        session=db,
        task_create=TaskCreate(
            title=title, parent_id=parent.id if parent else None, **fields
        ),
        project_id=project.id if project else None,
        owner_id=owner.id,
        reporter=crud.Reporter(user_id=owner.id),
    )


def _live_ids(db: Session, owner: User) -> set[uuid.UUID]:
    db.expire_all()
    return set(
        db.exec(
            select(Task.id).where(Task.owner_id == owner.id, crud.not_deleted(Task))
        ).all()
    )


def _event(db: Session, deletion_id: uuid.UUID) -> Deletion:
    return db.get_one(Deletion, deletion_id)


def _verdict(db: Session, owner: User, deletion_id: uuid.UUID) -> Any:
    db.expire_all()
    return deletions.restorability(db, owner.id, [deletion_id])[deletion_id]


def _agrees(db: Session, owner: User, deletion_id: uuid.UUID) -> Any:
    """Restore, checking first that "can restore" said what restoring did."""
    said = _verdict(db, owner, deletion_id)
    done = deletions.restore(db, owner.id, deletion_id)
    assert done.refusal == said.refusal
    assert done.restorable == said.restorable
    return done


# A task


def test_a_task_event_brings_back_exactly_its_rows(db: Session, owner: User) -> None:
    project = _project(db, owner)
    parent = _task(db, owner, project=project)
    kept = _task(db, owner, parent=parent, title="deleted on its own")
    child = _task(db, owner, parent=parent)
    grandchild = _task(db, owner, parent=child)
    alone = deletions.delete_task(db, kept)
    event_id = deletions.delete_task(db, parent)

    assert _event(db, event_id).task_id == parent.id
    assert deletions.kind_of(_event(db, event_id)) is DeletionKind.TASK
    assert _live_ids(db, owner) == set()

    verdict = _agrees(db, owner, event_id)

    assert verdict.restorable and verdict.refusal is None
    assert _live_ids(db, owner) == {parent.id, child.id, grandchild.id}
    # The subtask deleted on its own before stays deleted.
    assert _verdict(db, owner, alone).restorable


def test_a_restored_event_is_already_restored(db: Session, owner: User) -> None:
    task = _task(db, owner, project=_project(db, owner))
    event_id = deletions.delete_task(db, task)
    deletions.restore(db, owner.id, event_id)

    verdict = _agrees(db, owner, event_id)

    assert not verdict.restorable
    assert verdict.refusal is RestoreRefusal.ALREADY_RESTORED


def test_a_task_deleted_again_is_refused_from_the_older_event(
    db: Session, owner: User
) -> None:
    task = _task(db, owner, project=_project(db, owner))
    first = deletions.delete_task(db, task)
    deletions.restore(db, owner.id, first)
    second = deletions.delete_task(db, task)

    verdict = _agrees(db, owner, first)

    assert not verdict.restorable
    assert verdict.refusal is RestoreRefusal.DELETED_AGAIN
    assert _verdict(db, owner, second).refusal is None


def test_a_subtask_under_a_deleted_parent_is_refused(db: Session, owner: User) -> None:
    parent = _task(db, owner, project=_project(db, owner))
    child = _task(db, owner, parent=parent)
    alone = deletions.delete_task(db, child)
    deletions.delete_task(db, parent)

    verdict = _agrees(db, owner, alone)

    assert verdict.restorable
    assert verdict.refusal is RestoreRefusal.PARENT_DELETED
    assert child.id not in _live_ids(db, owner)


def test_a_task_in_a_deleted_project_is_refused(db: Session, owner: User) -> None:
    project = _project(db, owner)
    task = _task(db, owner, project=project)
    alone = deletions.delete_task(db, task)
    deletions.delete_project(db, project)

    assert _agrees(db, owner, alone).refusal is RestoreRefusal.PROJECT_DELETED


def test_a_task_in_an_archived_project_is_refused(db: Session, owner: User) -> None:
    project = _project(db, owner)
    task = _task(db, owner, project=project)
    event_id = deletions.delete_task(db, task)
    crud.set_project_archived(session=db, project=project, archived=True)

    verdict = _agrees(db, owner, event_id)

    assert verdict.refusal is RestoreRefusal.PROJECT_ARCHIVED
    assert verdict.project is not None and verdict.project.id == project.id
    assert task.id not in _live_ids(db, owner)


def _reopened_series(db: Session, owner: User, project: Project) -> Task:
    """A series whose next occurrence is deleted and whose first is open again."""
    first = _task(
        db,
        owner,
        project=project,
        title="Water plants",
        due_date=date(2030, 1, 7),
        recurrence=Recurrence(frequency=RecurrenceFrequency.WEEKLY),
    )
    crud.update_task(
        session=db, db_task=first, task_in=TaskUpdate(status=TaskStatus.DONE)
    )
    second = db.exec(
        select(Task).where(Task.series_id == first.series_id, crud.is_open(Task))
    ).one()
    return second


def _reopen(db: Session, task: Task) -> None:
    task.status = TaskStatus.TODO
    db.add(task)
    db.commit()


def test_a_task_that_would_reopen_a_series_is_refused(db: Session, owner: User) -> None:
    project = _project(db, owner)
    second = _reopened_series(db, owner, project)
    event_id = deletions.delete_task(db, second)
    first = db.exec(
        select(Task).where(
            Task.series_id == second.series_id, Task.status == TaskStatus.DONE
        )
    ).one()
    _reopen(db, first)

    verdict = _agrees(db, owner, event_id)

    assert verdict.refusal is RestoreRefusal.SERIES_HAS_OPEN_OCCURRENCE
    assert verdict.subject == "Water plants"


# A project


def test_a_project_event_brings_back_the_project_and_its_tasks(
    db: Session, owner: User
) -> None:
    project = _project(db, owner)
    kept = _task(db, owner, project=project, title="deleted on its own")
    root = _task(db, owner, project=project)
    child = _task(db, owner, parent=root)
    deletions.delete_task(db, kept)
    event_id = deletions.delete_project(db, project)

    assert deletions.kind_of(_event(db, event_id)) is DeletionKind.PROJECT
    verdict = _agrees(db, owner, event_id)

    assert verdict.restorable and verdict.refusal is None
    db.refresh(project)
    assert project.deletion_id is None
    assert _live_ids(db, owner) == {root.id, child.id}


def test_an_archived_project_comes_back_archived(db: Session, owner: User) -> None:
    project = _project(db, owner)
    _task(db, owner, project=project)
    crud.set_project_archived(session=db, project=project, archived=True)
    event_id = deletions.delete_project(db, project)

    assert _agrees(db, owner, event_id).refusal is None
    db.refresh(project)
    assert project.is_archived and project.deletion_id is None


def test_a_project_restore_twice_and_after_a_new_deletion(
    db: Session, owner: User
) -> None:
    project = _project(db, owner)
    first = deletions.delete_project(db, project)
    assert _verdict(db, owner, first).restorable
    deletions.restore(db, owner.id, first)
    assert _agrees(db, owner, first).refusal is RestoreRefusal.ALREADY_RESTORED

    deletions.delete_project(db, project)
    assert _agrees(db, owner, first).refusal is RestoreRefusal.DELETED_AGAIN


def test_a_project_that_would_reopen_a_series_is_refused_whole(
    db: Session, owner: User
) -> None:
    project = _project(db, owner)
    other = _project(db, owner, "Elsewhere")
    second = _reopened_series(db, owner, project)
    first = db.exec(
        select(Task).where(
            Task.series_id == second.series_id, Task.status == TaskStatus.DONE
        )
    ).one()
    first.project_id = other.id
    db.add(first)
    db.commit()
    event_id = deletions.delete_project(db, project)
    _reopen(db, first)

    verdict = _agrees(db, owner, event_id)

    assert verdict.refusal is RestoreRefusal.SERIES_HAS_OPEN_OCCURRENCE
    assert verdict.subject == "Home"
    db.refresh(project)
    assert project.deletion_id is not None


# A batch


def test_a_batch_brings_back_its_selection_and_their_subtasks(
    db: Session, owner: User
) -> None:
    project = _project(db, owner)
    a = _task(db, owner, project=project)
    a_child = _task(db, owner, parent=a)
    b = _task(db, owner, project=project)
    untouched = _task(db, owner, project=project)
    event_id = deletions.delete_tasks(db, [a, b])

    assert deletions.kind_of(_event(db, event_id)) is DeletionKind.BATCH
    assert deletions.marked_task_ids(db, event_id) == {a.id, a_child.id, b.id}
    assert _live_ids(db, owner) == {untouched.id}

    assert _agrees(db, owner, event_id).refusal is None
    assert _live_ids(db, owner) == {a.id, a_child.id, b.id, untouched.id}
    assert _agrees(db, owner, event_id).refusal is RestoreRefusal.ALREADY_RESTORED


def test_a_batch_checks_only_the_tasks_whose_parent_it_did_not_take(
    db: Session, owner: User
) -> None:
    project = _project(db, owner)
    parent = _task(db, owner, project=project)
    child = _task(db, owner, parent=parent)
    orphan_parent = _task(db, owner, project=project)
    orphan = _task(db, owner, parent=orphan_parent, title="Orphan")
    event_id = deletions.delete_tasks(db, [parent, child])
    assert _agrees(db, owner, event_id).refusal is None

    event_id = deletions.delete_tasks(db, [orphan])
    deletions.delete_task(db, orphan_parent)
    verdict = _agrees(db, owner, event_id)
    assert verdict.refusal is RestoreRefusal.PARENT_DELETED
    assert verdict.subject == "Orphan"


def test_a_batch_in_an_archived_project_is_refused(db: Session, owner: User) -> None:
    project = _project(db, owner)
    task = _task(db, owner, project=project)
    event_id = deletions.delete_tasks(db, [task])
    crud.set_project_archived(session=db, project=project, archived=True)

    assert _agrees(db, owner, event_id).refusal is RestoreRefusal.PROJECT_ARCHIVED


# Cost


@pytest.fixture
def statements(db: Session) -> Iterator[list[str]]:
    recorded: list[str] = []
    engine = db.get_bind()

    def record(*args: Any) -> None:
        recorded.append(str(args[2]))

    event.listen(engine, "before_cursor_execute", record)
    yield recorded
    event.remove(engine, "before_cursor_execute", record)


def test_a_page_of_events_costs_a_fixed_number_of_queries(
    db: Session, owner: User, statements: list[str]
) -> None:
    project = _project(db, owner)

    def events(count: int) -> list[uuid.UUID]:
        made = []
        for _ in range(count):
            parent = _task(db, owner, project=project)
            _task(db, owner, parent=_task(db, owner, parent=parent))
            made.append(deletions.delete_task(db, parent))
            made.append(deletions.delete_tasks(db, [_task(db, owner, project=project)]))
            made.append(deletions.delete_project(db, _project(db, owner)))
        return made

    few, many = events(1), events(10)

    def cost(ids: list[uuid.UUID]) -> int:
        db.expire_all()
        statements.clear()
        deletions.restorability(db, owner.id, ids)
        return len(statements)

    assert cost(few) == cost(many)
