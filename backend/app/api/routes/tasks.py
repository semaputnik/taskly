import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import case
from sqlmodel import func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_owned_project
from app.models import (
    Task,
    TaskCreate,
    TaskPriority,
    TaskPublic,
    TasksPublic,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Unset priority sorts as P4 (lowest) without being reported as P4.
_PRIORITY_RANK = case(
    (Task.priority == TaskPriority.P1, 1),  # type: ignore[arg-type]
    (Task.priority == TaskPriority.P2, 2),  # type: ignore[arg-type]
    (Task.priority == TaskPriority.P3, 3),  # type: ignore[arg-type]
    else_=4,
)


def _get_owned_task(
    session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Task:
    task = session.get(Task, task_id)
    if not task or task.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _check_assignee(current_user: CurrentUser, assignee_id: uuid.UUID | None) -> None:
    if assignee_id is not None and assignee_id != current_user.id:
        raise HTTPException(
            status_code=400, detail="A task can only be assigned to yourself"
        )


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the current user's tasks, across all of their projects.
    """
    count_statement = (
        select(func.count())
        .select_from(Task)
        .where(Task.owner_id == current_user.id)
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Task)
        .where(Task.owner_id == current_user.id)
        .order_by(_PRIORITY_RANK, Task.created_at)  # type: ignore[arg-type]
        .offset(skip)
        .limit(limit)
    )
    tasks = session.exec(statement).all()
    return TasksPublic(data=tasks, count=count)


@router.post("/", response_model=TaskPublic)
def create_task(
    *, session: SessionDep, current_user: CurrentUser, task_in: TaskCreate
) -> Any:
    """
    Create a task. A task created without a project lands in the Inbox.
    """
    if task_in.project_id is not None:
        project = get_owned_project(session, current_user, task_in.project_id)
    else:
        project = crud.get_inbox_project(session=session, owner_id=current_user.id)

    _check_assignee(current_user, task_in.assignee_id)

    return crud.create_task(
        session=session,
        task_create=task_in,
        project_id=project.id,
        owner_id=current_user.id,
    )


@router.get("/{task_id}", response_model=TaskPublic)
def read_task(
    *, session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Any:
    """
    Retrieve a single task.
    """
    return _get_owned_task(session, current_user, task_id)


@router.patch("/{task_id}", response_model=TaskPublic)
def update_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
) -> Any:
    """
    Update a task: its fields, completion state, assignee, or project.
    """
    task = _get_owned_task(session, current_user, task_id)

    if "project_id" in task_in.model_fields_set:
        if task_in.project_id is None:
            raise HTTPException(
                status_code=400, detail="A task must belong to a project"
            )
        get_owned_project(session, current_user, task_in.project_id)

    if "assignee_id" in task_in.model_fields_set:
        _check_assignee(current_user, task_in.assignee_id)

    return crud.update_task(session=session, db_task=task, task_in=task_in)
