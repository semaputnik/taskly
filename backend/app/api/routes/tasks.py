import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_owned_project, get_owned_task
from app.models import (
    Message,
    SubtaskCompletion,
    Task,
    TaskCreate,
    TaskPublic,
    TaskQuery,
    TasksPublic,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Refusing to complete a parent with open subtasks is a state conflict the
# client can resolve, not a malformed request: it gets its own status code and
# a code the frontend matches on to raise the prompt (FR-02.5, FR-02.6).
UNCOMPLETED_SUBTASKS_STATUS = 409
UNCOMPLETED_SUBTASKS_CODE = "task_has_uncompleted_subtasks"

# Deleting takes the whole subtree with it, so the same shape of refusal guards
# it: the request has to confirm the cascade before anything goes (FR-01.12).
HAS_SUBTASKS_STATUS = 409
HAS_SUBTASKS_CODE = "task_has_subtasks"


def _unique(names: list[str]) -> list[str]:
    """
    Tag names with repeats dropped, keeping the order they were sent in. They
    arrive trimmed and non-blank from `TagName`; the same name twice is the one
    thing left that a task cannot store.
    """
    return list(dict.fromkeys(names))


def _check_assignee(current_user: CurrentUser, assignee_id: uuid.UUID | None) -> None:
    if assignee_id is not None and assignee_id != current_user.id:
        raise HTTPException(
            status_code=400, detail="A task can only be assigned to yourself"
        )


def _public(task: Task, *, project_id: uuid.UUID, tags: list[str]) -> TaskPublic:
    """
    A task as the API reports it, with the project it resolves to and its tags
    filled in. Listings resolve both in bulk; `_read` does one task.
    """
    return TaskPublic.model_validate(
        task, update={"project_id": project_id, "tags": tags}
    )


def _read(session: SessionDep, task: Task) -> TaskPublic:
    """One task, with everything the API reports about it looked up."""
    return _public(
        task,
        project_id=crud.get_task_project_id(session=session, task=task),
        tags=crud.get_task_tags(session=session, task_ids=[task.id])[task.id],
    )


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep,
    current_user: CurrentUser,
    query: Annotated[TaskQuery, Query()],
) -> Any:
    """
    Retrieve the current user's tasks, across all of their projects, narrowed
    and ordered by the query.
    """
    if query.project_id is not None:
        # 404 rather than an empty list: a project the user cannot see is not a
        # project with no tasks.
        get_owned_project(session, current_user, query.project_id)

    tasks, count = crud.get_tasks(
        session=session, owner_id=current_user.id, query=query
    )
    project_ids = crud.get_task_project_ids(session=session, owner_id=current_user.id)
    tags = crud.get_task_tags(session=session, task_ids=[task.id for task in tasks])
    return TasksPublic(
        data=[
            _public(task, project_id=project_ids[task.id], tags=tags[task.id])
            for task in tasks
        ],
        count=count,
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
        # Checks the parent is the user's and still there; the subtask's own
        # project is then derived from it.
        get_owned_task(session, current_user, task_in.parent_id)
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
            tag_names=_unique(task_in.tags),
        )
        return _read(session, task)

    if task_in.project_id is not None:
        project = get_owned_project(session, current_user, task_in.project_id)
    else:
        project = crud.get_inbox_project(session=session, owner_id=current_user.id)

    task = crud.create_task(
        session=session,
        task_create=task_in,
        project_id=project.id,
        owner_id=current_user.id,
        tag_names=_unique(task_in.tags),
    )
    return _read(session, task)


@router.get("/{task_id}", response_model=TaskPublic)
def read_task(
    *, session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Any:
    """
    Retrieve a single task.
    """
    return _read(session, get_owned_task(session, current_user, task_id))


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
    task = get_owned_task(session, current_user, task_id)
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

    if task_in.tags is not None:
        crud.set_task_tags(session=session, task=task, names=_unique(task_in.tags))

    return _public(
        task,
        project_id=project_id,
        tags=crud.get_task_tags(session=session, task_ids=[task.id])[task.id],
    )


@router.delete("/{task_id}")
def delete_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    delete_subtasks: bool = False,
) -> Message:
    """
    Delete a task, and its subtasks with it.

    The rows are marked deleted rather than removed, so the deletion can be
    reversed from the activity log later (FR-01.8). Because the cascade can
    take down far more than the task named here, a task that still has subtasks
    is only deleted when `delete_subtasks` says so (FR-01.11, FR-01.12).
    """
    task = get_owned_task(session, current_user, task_id)

    if not delete_subtasks and crud.has_subtasks(session=session, task=task):
        raise HTTPException(
            status_code=HAS_SUBTASKS_STATUS,
            detail={
                "code": HAS_SUBTASKS_CODE,
                "message": (
                    "This task has subtasks, which would be deleted with it. "
                    "Confirm with delete_subtasks to go ahead."
                ),
            },
        )

    crud.delete_task(session=session, task=task)
    return Message(message="Task deleted successfully")
