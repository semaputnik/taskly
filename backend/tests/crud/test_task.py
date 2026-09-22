import datetime
import uuid

from sqlmodel import Session

from app import crud, deletions
from app.models import (
    ProjectCreate,
    Task,
    TaskCreate,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
    UserCreate,
)
from tests.utils.utils import random_email, random_lower_string


def test_get_inbox_project(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)

    inbox = crud.get_inbox_project(session=db, owner_id=user.id)

    assert inbox.is_inbox is True
    assert inbox.owner_id == user.id


def test_create_task(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)

    task_in = TaskCreate(
        title="Buy milk",
        description="2%",
        due_date=datetime.date(2026, 1, 1),
        priority=TaskPriority.P2,
    )
    task = crud.create_task(
        session=db,
        task_create=task_in,
        project_id=inbox.id,
        owner_id=user.id,
        reporter=crud.Reporter(user_id=user.id),
    )

    assert task.title == "Buy milk"
    assert task.description == "2%"
    assert task.due_date == datetime.date(2026, 1, 1)
    assert task.priority == TaskPriority.P2
    assert task.status is TaskStatus.TODO
    assert task.project_id == inbox.id
    assert task.owner_id == user.id
    assert task.assignee_id is None


def test_create_task_with_no_priority_stays_unset(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)

    task = crud.create_task(
        session=db,
        task_create=TaskCreate(title="Untitled priority"),
        project_id=inbox.id,
        owner_id=user.id,
        reporter=crud.Reporter(user_id=user.id),
    )

    assert task.priority is None


def test_update_task_fields(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)
    task = crud.create_task(
        session=db,
        task_create=TaskCreate(title="Old title"),
        project_id=inbox.id,
        owner_id=user.id,
        reporter=crud.Reporter(user_id=user.id),
    )

    updated = crud.update_task(
        session=db,
        db_task=task,
        task_in=TaskUpdate(
            title="New title",
            priority=TaskPriority.P1,
            due_date=datetime.date(2026, 2, 2),
            assignee_id=user.id,
        ),
        assignee=crud.Assignee(user_id=user.id),
    )

    assert updated.title == "New title"
    assert updated.priority == TaskPriority.P1
    assert updated.due_date == datetime.date(2026, 2, 2)
    assert updated.assignee_id == user.id


def test_complete_and_return_to_not_completed(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)
    task = crud.create_task(
        session=db,
        task_create=TaskCreate(title="Do the thing"),
        project_id=inbox.id,
        owner_id=user.id,
        reporter=crud.Reporter(user_id=user.id),
    )

    completed = crud.update_task(
        session=db, db_task=task, task_in=TaskUpdate(status=TaskStatus.DONE)
    )
    assert completed.status is TaskStatus.DONE

    not_completed = crud.update_task(
        session=db, db_task=completed, task_in=TaskUpdate(status=TaskStatus.TODO)
    )
    assert not_completed.status is TaskStatus.TODO


def test_move_task_to_another_project(db: Session) -> None:
    user_in = UserCreate(email=random_email(), password=random_lower_string())
    user = crud.create_user(session=db, user_create=user_in)
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)
    other_project = crud.create_project(
        session=db, project_create=ProjectCreate(name="Work"), owner_id=user.id
    )
    task = crud.create_task(
        session=db,
        task_create=TaskCreate(title="Move me"),
        project_id=inbox.id,
        owner_id=user.id,
        reporter=crud.Reporter(user_id=user.id),
    )

    moved = crud.update_task(
        session=db,
        db_task=task,
        task_in=TaskUpdate(project_id=other_project.id),
    )

    assert moved.project_id == other_project.id


def _tree(db: Session, depth: int) -> tuple[uuid.UUID, list[Task]]:
    """A chain of `depth` tasks, the first a root in a new project."""
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    project = crud.create_project(
        session=db, project_create=ProjectCreate(name="Deep"), owner_id=user.id
    )
    chain = [
        crud.create_task(
            session=db,
            task_create=TaskCreate(title="Level 0"),
            project_id=project.id,
            owner_id=user.id,
            reporter=crud.Reporter(user_id=user.id),
        )
    ]
    for level in range(1, depth):
        chain.append(
            crud.create_task(
                session=db,
                task_create=TaskCreate(title=f"Level {level}", parent_id=chain[-1].id),
                project_id=None,
                owner_id=user.id,
                reporter=crud.Reporter(user_id=user.id),
            )
        )
    return project.id, chain


def test_task_project_ids_resolve_a_deep_subtask_through_its_root(
    db: Session,
) -> None:
    project_id, chain = _tree(db, depth=6)

    resolved = crud.get_task_project_ids(
        session=db, owner_id=chain[0].owner_id, task_ids=[chain[-1].id, chain[2].id]
    )

    # Only what was asked about, each at its root's project.
    assert resolved == {chain[-1].id: project_id, chain[2].id: project_id}


def test_task_project_ids_leave_out_tasks_under_a_deleted_ancestor(
    db: Session,
) -> None:
    project_id, chain = _tree(db, depth=4)
    deletions.delete_task(db, chain[1])
    db.commit()

    resolved = crud.get_task_project_ids(
        session=db,
        owner_id=chain[0].owner_id,
        task_ids=[task.id for task in chain],
    )

    assert resolved == {chain[0].id: project_id}


def test_task_project_ids_do_not_reach_another_users_tasks(db: Session) -> None:
    _, chain = _tree(db, depth=2)
    stranger = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )

    assert (
        crud.get_task_project_ids(
            session=db, owner_id=stranger.id, task_ids=[task.id for task in chain]
        )
        == {}
    )
    assert (
        crud.get_task_project_ids(session=db, owner_id=stranger.id, task_ids=[]) == {}
    )
