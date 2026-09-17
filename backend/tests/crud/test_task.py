import datetime

from sqlmodel import Session

from app import crud
from app.models import (
    ProjectCreate,
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
        session=db, task_create=task_in, project_id=inbox.id, owner_id=user.id
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
    )

    moved = crud.update_task(
        session=db,
        db_task=task,
        task_in=TaskUpdate(project_id=other_project.id),
    )

    assert moved.project_id == other_project.id
