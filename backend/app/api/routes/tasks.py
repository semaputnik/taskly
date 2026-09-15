import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app import crud
from app.api import authorization
from app.api.authorization import TaskAction
from app.api.deps import (
    Caller,
    CallerDep,
    SessionDep,
    require_project_writable,
    require_task_writable,
)
from app.models import (
    BotUser,
    BotUserRef,
    Message,
    Recurrence,
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

# Moving an open occurrence's due date means something different for the rest
# of its series depending on the scope, so a request that does not say which
# is malformed rather than defaulted (FR-01.17).
DUE_DATE_SCOPE_REQUIRED_STATUS = 400
DUE_DATE_SCOPE_REQUIRED_CODE = "due_date_scope_required"

# A later occurrence already exists: reopening this one would leave the series
# with two open occurrences (FR-01.16).
OCCURRENCE_SUPERSEDED_STATUS = 409
OCCURRENCE_SUPERSEDED_CODE = "occurrence_superseded"


def _unique(names: list[str]) -> list[str]:
    """
    Tag names with repeats dropped, keeping the order they were sent in. They
    arrive trimmed and non-blank from `TagName`; the same name twice is the one
    thing left that a task cannot store.
    """
    return list(dict.fromkeys(names))


def _resolve_assignee(
    session: SessionDep,
    caller: Caller,
    assignee_id: uuid.UUID | None,
    current: crud.Assignee | None = None,
) -> crud.Assignee:
    """
    Who `assignee_id` names: the owner, or one of the owner's bot users
    (FR-01.7) — never another user or their bot users.

    A deleted bot user takes no new tasks, but stays on the ones it already
    has (FR-08.21), so resending `current` is not a new assignment.
    """
    if assignee_id is None:
        return crud.Assignee()
    if assignee_id == caller.owner_id:
        return crud.Assignee(user_id=assignee_id)
    bot = session.get(BotUser, assignee_id)
    if bot is None or bot.owner_id != caller.owner_id:
        raise HTTPException(
            status_code=400,
            detail="A task can only be assigned to you or to one of your bot users",
        )
    assignee = crud.Assignee(bot_user_id=bot.id)
    if bot.deleted_at is not None and assignee != current:
        raise HTTPException(
            status_code=400,
            detail=f"The bot user “{bot.name}” is deleted and takes no new tasks",
        )
    return assignee


def _check_recurrence(
    *, parent_id: uuid.UUID | None, recurrence: Recurrence | None, due_date: date | None
) -> None:
    """
    A recurring task is a root task with a due date: its next occurrence's due
    date is counted from this one's, and a subtask's routine is its root's.
    """
    if recurrence is None:
        return
    if parent_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Only a task at the top of its tree can recur",
        )
    if due_date is None:
        raise HTTPException(status_code=400, detail="A recurring task needs a due date")


def _public(
    task: Task,
    *,
    project_id: uuid.UUID,
    tags: list[str],
    recurrence: Recurrence | None,
    bot_users: dict[uuid.UUID, BotUserRef],
) -> TaskPublic:
    """
    A task as the API reports it, with the project it resolves to, its tags,
    its recurrence and its assignee filled in. Listings resolve them in bulk;
    `_read` does one task.
    """
    return TaskPublic.model_validate(
        task,
        update={
            "project_id": project_id,
            "tags": tags,
            "recurrence": recurrence,
            "assignee_id": task.assignee_id or task.assignee_bot_user_id,
            "assignee_bot_user": bot_users.get(task.assignee_bot_user_id)
            if task.assignee_bot_user_id
            else None,
        },
    )


def _read(session: SessionDep, task: Task) -> TaskPublic:
    """One task, with everything the API reports about it looked up."""
    return _public(
        task,
        project_id=crud.get_task_project_id(session=session, task=task),
        tags=crud.get_task_tags(session=session, task_ids=[task.id])[task.id],
        recurrence=crud.get_recurrences(session=session, tasks=[task])[task.id],
        bot_users=crud.get_bot_user_refs(
            session=session, bot_user_ids=[task.assignee_bot_user_id]
        ),
    )


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep,
    caller: CallerDep,
    query: Annotated[TaskQuery, Query()],
) -> Any:
    """
    Retrieve the current user's tasks, across all of their projects, narrowed
    and ordered by the query.

    A bot user gets only the tasks of the projects in its scope, and never the
    archive.
    """
    if query.archived:
        authorization.refuse_archived_for_bot(caller)
    if query.project_id is not None:
        # 404 rather than an empty list: a project the user cannot see is not a
        # project with no tasks.
        authorization.get_project(session, caller, query.project_id)
    else:
        authorization.authorize_tasks(caller, TaskAction.READ)

    tasks, count = crud.get_tasks(
        session=session,
        owner_id=caller.owner_id,
        query=query,
        project_ids=caller.project_ids if caller.bot else None,
    )
    project_ids = crud.get_task_project_ids(session=session, owner_id=caller.owner_id)
    tags = crud.get_task_tags(session=session, task_ids=[task.id for task in tasks])
    recurrences = crud.get_recurrences(session=session, tasks=tasks)
    bot_users = crud.get_bot_user_refs(
        session=session, bot_user_ids=[task.assignee_bot_user_id for task in tasks]
    )
    return TasksPublic(
        data=[
            _public(
                task,
                project_id=project_ids[task.id],
                tags=tags[task.id],
                recurrence=recurrences[task.id],
                bot_users=bot_users,
            )
            for task in tasks
        ],
        count=count,
    )


@router.post("/", response_model=TaskPublic)
def create_task(*, session: SessionDep, caller: CallerDep, task_in: TaskCreate) -> Any:
    """
    Create a task, or a subtask of one. A task created without a project lands
    in the Inbox; a subtask follows its parent's project instead.

    A task created with a recurrence is the first occurrence of its series.

    A bot user creates only where its scope reaches — the Inbox included, which
    has to be in its scope like any other project — and sets no tags.
    """
    # Where the task goes is settled first, so a bot user is refused by its
    # scope before anything about the request itself is looked at.
    parent: Task | None = None
    if task_in.parent_id is not None:
        parent = authorization.get_task(
            session, caller, task_in.parent_id, TaskAction.CREATE
        )
    elif task_in.project_id is not None:
        project = authorization.get_project(
            session, caller, task_in.project_id, TaskAction.CREATE
        )
    else:
        project = crud.get_inbox_project(session=session, owner_id=caller.owner_id)
        authorization.authorize_tasks(caller, TaskAction.CREATE, project)
    authorization.refuse_tag_changes_for_bot(caller, task_in.model_fields_set)

    assignee = _resolve_assignee(session, caller, task_in.assignee_id)
    _check_recurrence(
        parent_id=task_in.parent_id,
        recurrence=task_in.recurrence,
        due_date=task_in.due_date,
    )

    if parent is not None:
        require_task_writable(session, parent.id)
        if task_in.project_id is not None:
            raise HTTPException(
                status_code=400,
                detail="A subtask belongs to the project of its parent",
            )
        # The subtask's own project is derived from its parent's tree.
        project_id = None
    else:
        require_project_writable(project)
        project_id = project.id

    task = crud.create_task(
        session=session,
        task_create=task_in,
        project_id=project_id,
        owner_id=caller.owner_id,
        assignee=assignee,
        tag_names=_unique(task_in.tags),
    )
    return _read(session, task)


@router.get("/{task_id}", response_model=TaskPublic)
def read_task(*, session: SessionDep, caller: CallerDep, task_id: uuid.UUID) -> Any:
    """
    Retrieve a single task.
    """
    task = authorization.get_task(session, caller, task_id, TaskAction.READ)
    return _read(session, task)


@router.patch("/{task_id}", response_model=TaskPublic)
def update_task(
    *,
    session: SessionDep,
    caller: CallerDep,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
) -> Any:
    """
    Update a task: its fields, completion state, assignee, or project.

    Completing a task that still has uncompleted subtasks is refused unless the
    request says what happens to them, through `subtasks`.

    Completing an occurrence of a recurring task creates the next one. Moving
    the due date of an open occurrence needs `due_date_scope` to say whether
    the rest of the series moves with it.

    A bot user needs the task in its scope and, to move it, the destination
    too (FR-08.8); it sets no tags.
    """
    task = authorization.get_task(session, caller, task_id, TaskAction.UPDATE)
    authorization.refuse_tag_changes_for_bot(caller, task_in.model_fields_set)
    require_task_writable(session, task.id)
    project_id = crud.get_task_project_id(session=session, task=task)
    _check_recurrence_update(session=session, task=task, task_in=task_in)

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
        # Moving a task in is as much a change to the destination as creating
        # one there. For a bot the source was checked with the task, so work
        # can neither leave its scope nor enter from outside it.
        require_project_writable(
            authorization.get_project(
                session, caller, task_in.project_id, TaskAction.UPDATE
            )
        )
        project_id = task_in.project_id

    assignee = None
    if "assignee_id" in task_in.model_fields_set:
        assignee = _resolve_assignee(
            session,
            caller,
            task_in.assignee_id,
            current=crud.Assignee(task.assignee_id, task.assignee_bot_user_id),
        )

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

    task = crud.update_task(
        session=session,
        db_task=task,
        task_in=task_in,
        assignee=assignee,
        tag_names=_unique(task_in.tags) if task_in.tags is not None else None,
    )

    return _public(
        task,
        project_id=project_id,
        tags=crud.get_task_tags(session=session, task_ids=[task.id])[task.id],
        recurrence=crud.get_recurrences(session=session, tasks=[task])[task.id],
        bot_users=crud.get_bot_user_refs(
            session=session, bot_user_ids=[task.assignee_bot_user_id]
        ),
    )


def _check_recurrence_update(
    *, session: SessionDep, task: Task, task_in: TaskUpdate
) -> None:
    """Everything an update has to get right about the task's series."""
    fields_set = task_in.model_fields_set
    current = crud.get_recurrences(session=session, tasks=[task])[task.id]
    recurrence = task_in.recurrence if "recurrence" in fields_set else current
    due_date = task_in.due_date if "due_date" in fields_set else task.due_date
    recurrence_changes = recurrence != current

    if recurrence_changes:
        if task.completed:
            # Its series has already moved on, or it would start one that
            # nothing ever completes into a next occurrence.
            raise HTTPException(
                status_code=400,
                detail="Only a task that is not completed can change how it recurs",
            )
        _check_recurrence(
            parent_id=task.parent_id, recurrence=recurrence, due_date=due_date
        )
    elif recurrence is not None and due_date is None:
        raise HTTPException(status_code=400, detail="A recurring task needs a due date")

    # A new rule restarts the schedule from this occurrence anyway, so only a
    # date moving on its own asks what happens to the rest of the series.
    reschedules = (
        current is not None
        and not task.completed
        and not recurrence_changes
        and due_date != task.due_date
    )
    if reschedules and task_in.due_date_scope is None:
        raise HTTPException(
            status_code=DUE_DATE_SCOPE_REQUIRED_STATUS,
            detail={
                "code": DUE_DATE_SCOPE_REQUIRED_CODE,
                "message": (
                    "This task recurs. Say whether the new due date applies to "
                    "this occurrence only or to this and all following ones."
                ),
            },
        )
    if not reschedules and task_in.due_date_scope is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "`due_date_scope` only applies to changing the due date of a "
                "recurring task that is not completed"
            ),
        )

    if (
        task_in.completed is False
        and task.completed
        and crud.is_superseded(session=session, task=task)
    ):
        raise HTTPException(
            status_code=OCCURRENCE_SUPERSEDED_STATUS,
            detail={
                "code": OCCURRENCE_SUPERSEDED_CODE,
                "message": (
                    "A later occurrence of this recurring task already exists. "
                    "Only the latest occurrence can be returned to not completed."
                ),
            },
        )


@router.delete("/{task_id}")
def delete_task(
    *,
    session: SessionDep,
    caller: CallerDep,
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
    task = authorization.get_task(session, caller, task_id, TaskAction.DELETE)
    require_task_writable(session, task.id)

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
