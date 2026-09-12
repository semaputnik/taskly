import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import case
from sqlmodel import func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_owned_project
from app.models import (
    SubtaskCompletion,
    Task,
    TaskCreate,
    TaskPriority,
    TaskPublic,
    TasksPublic,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Refusing to complete a parent with open subtasks is a state conflict the
# client can resolve, not a malformed request: it gets its own status code and
# a code the frontend matches on to raise the prompt (FR-02.5, FR-02.6).
UNCOMPLETED_SUBTASKS_STATUS = 409
UNCOMPLETED_SUBTASKS_CODE = "task_has_uncompleted_subtasks"

# Unset priority sorts as P4 (lowest) without being reported as P4.
_PRIORITY_RANK = case(
    (Task.priority == TaskPriority.P1, 1),  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
    (Task.priority == TaskPriority.P2, 2),  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
    (Task.priority == TaskPriority.P3, 3),  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
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


def _public(task: Task, project_id: uuid.UUID) -> TaskPublic:
    """
    A task as the API reports it, with the project it resolves to filled in.
    """
    return TaskPublic.model_validate(task, update={"project_id": project_id})


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the current user's tasks, across all of their projects.
    """
    count_statement = (
        select(func.count()).select_from(Task).where(Task.owner_id == current_user.id)
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Task)
        .where(Task.owner_id == current_user.id)
        .order_by(_PRIORITY_RANK, Task.created_at)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
        .offset(skip)
        .limit(limit)
    )
    tasks = session.exec(statement).all()
    project_ids = crud.get_task_project_ids(session=session, owner_id=current_user.id)
    return TasksPublic(
        data=[_public(task, project_ids[task.id]) for task in tasks], count=count
    )


@router.post("/", response_model=TaskPublic)
def create_task(
    *, session: SessionDep, current_user: CurrentUser, task_in: TaskCreate
) -> Any:
    """
    Create a task, or a subtask of one. A task created without a project lands
    in the Inbox; a subtask follows its parent's project instead.
    """
    _check_assignee(current_user, task_in.assignee_id)

    if task_in.parent_id is not None:
        parent = _get_owned_task(session, current_user, task_in.parent_id)
        if task_in.project_id is not None:
            raise HTTPException(
                status_code=400,
                detail="A subtask belongs to the project of its parent",
            )
        task = crud.create_task(
            session=session,
            task_create=task_in,
            project_id=None,
            owner_id=current_user.id,
        )
        return _public(task, crud.get_task_project_id(session=session, task=parent))

    if task_in.project_id is not None:
        project = get_owned_project(session, current_user, task_in.project_id)
    else:
        project = crud.get_inbox_project(session=session, owner_id=current_user.id)

    task = crud.create_task(
        session=session,
        task_create=task_in,
        project_id=project.id,
        owner_id=current_user.id,
    )
    return _public(task, project.id)


@router.get("/{task_id}", response_model=TaskPublic)
def read_task(
    *, session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Any:
    """
    Retrieve a single task.
    """
    task = _get_owned_task(session, current_user, task_id)
    return _public(task, crud.get_task_project_id(session=session, task=task))


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

    Completing a task that still has uncompleted subtasks is refused unless the
    request says what happens to them, through `subtasks`.
    """
    task = _get_owned_task(session, current_user, task_id)
    project_id = crud.get_task_project_id(session=session, task=task)

    if "project_id" in task_in.model_fields_set:
        if task_in.project_id is None:
            raise HTTPException(
                status_code=400, detail="A task must belong to a project"
            )
        if task.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A subtask follows its parent's project; move the task at "
                    "the top of the tree instead"
                ),
            )
        get_owned_project(session, current_user, task_in.project_id)
        project_id = task_in.project_id

    if "assignee_id" in task_in.model_fields_set:
        _check_assignee(current_user, task_in.assignee_id)

    if task_in.subtasks is not None and task_in.completed is not True:
        raise HTTPException(
            status_code=400,
            detail="`subtasks` only applies to a request that completes the task",
        )

    if task_in.completed is True and crud.has_uncompleted_subtasks(
        session=session, task=task
    ):
        if task_in.subtasks is None:
            raise HTTPException(
                status_code=UNCOMPLETED_SUBTASKS_STATUS,
                detail={
                    "code": UNCOMPLETED_SUBTASKS_CODE,
                    "message": (
                        "This task has uncompleted subtasks. Say whether they "
                        "stay uncompleted or are completed too."
                    ),
                },
            )
        if task_in.subtasks is SubtaskCompletion.COMPLETE:
            crud.complete_subtasks(session=session, task=task)

    task = crud.update_task(session=session, db_task=task, task_in=task_in)
    return _public(task, project_id)
