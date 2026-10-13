"""
`create_task` (spec #247, #255): file a task, a subtask or a recurring one.

Calls `app.tasks.create` directly (#275, #281): the Inbox default for a task
created without a project, a subtask's own project, the assignee, the
reporter, the tag grant and the recurrence checks are all that operation's
own rules now, the same ones a human's `POST /tasks` goes through — neither
a route function nor a route-private constant is imported here any more.
This tool's own job is only to translate its MCP-style arguments (a project
by name or id, a parent task by a full id or the short prefix a compact line
prints, an assignee as `self`, `owner` or an id, a due date read by
`app.mcp.conventions.resolve_date`) into the `TaskCreate` that operation
already takes.
"""

from typing import Annotated, Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from pydantic import Field
from sqlmodel import Session

from app import tasks
from app.api.deps import Caller
from app.mcp.conventions import (
    open_caller,
    refusal,
    refuse,
    resolve_assignee,
    resolve_date,
    resolve_project_id,
    resolve_task_id,
)
from app.mcp.server import mcp_server
from app.models import (
    Recurrence,
    TagName,
    TaskCreate,
    TaskPriority,
    TaskStatus,
)
from app.read_models import task_publics
from app.refusals import Refusal


@mcp_server.tool()
def create_task(
    ctx: Context,
    title: Annotated[str, Field(max_length=255)],
    description: Annotated[str, Field(max_length=2000)] | None = None,
    project: str | None = None,
    parent_task_id: str | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    due_date: str | None = None,
    tags: list[TagName] | None = None,
    assignee: str | None = None,
    recurrence: Recurrence | None = None,
) -> dict[str, Any]:
    """
    File a task, a subtask of one, or the first occurrence of a recurring
    series — in one call, with the fields the task list itself has: a title,
    a description, a due date, a priority, tags and an assignee.

    `project` takes a name, case-insensitively, or an id; leaving it out
    lands the task in the Inbox, which has to be in this bot user's scope
    like any other project. `parent_task_id` takes a full id or the short
    prefix a compact line's own `id` prints, and makes this a subtask, which
    always takes its parent's project — naming `project` alongside it is
    refused rather than picked between. A task starts in `backlog` unless
    `status` names another.

    `due_date` takes an ISO date, `today`, `tomorrow`, or `+<count>d`, read
    against the server's own date. `tags` are applied by name; a name that
    is not a tag of this owner's yet needs the `create_tags` grant, and the
    refusal names which of the sent names were new.

    `assignee` takes `self` (this bot user), `owner` (the human who owns
    this account), or a bot user's id — never another user's. A deleted bot
    user takes no new task. The reporter is always this bot user; no
    argument can set it.

    `recurrence` makes this the first occurrence of a series: `{"frequency":
    "daily"|"weekly"|"monthly"|"every_n_days", "interval_days": N}` (only
    `every_n_days` takes `interval_days`, at least 2). A recurring task needs
    a due date, must be a task rather than a subtask, and cannot be created
    `done` — each refused as such.

    Returns the created task in full, with its id, so it can be acted on
    immediately.
    """
    with open_caller(ctx) as (session, caller):
        return create_task_body(
            session,
            caller,
            title=title,
            description=description,
            project=project,
            parent_task_id=parent_task_id,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags,
            assignee=assignee,
            recurrence=recurrence,
        )


def create_task_body(
    session: Session,
    caller: Caller,
    *,
    title: str,
    description: str | None = None,
    project: str | None = None,
    parent_task_id: str | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    due_date: str | None = None,
    tags: list[TagName] | None = None,
    assignee: str | None = None,
    recurrence: Recurrence | None = None,
) -> dict[str, Any]:
    """`create_task`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    if parent_task_id is not None and project is not None:
        refuse(
            "invalid_argument",
            "A subtask belongs to the project of its parent; name no project for it.",
        )

    try:
        project_id = (
            resolve_project_id(session, caller, project) if project is not None else None
        )
        parent_id = (
            resolve_task_id(session, caller, parent_task_id)
            if parent_task_id is not None
            else None
        )
        due = resolve_date(due_date) if due_date is not None else None
        assignee_id = resolve_assignee(caller, assignee)

        task_in = TaskCreate(
            title=title,
            description=description,
            due_date=due,
            priority=priority,
            tags=tags or [],
            project_id=project_id,
            parent_id=parent_id,
            assignee_id=assignee_id,
            recurrence=recurrence,
            status=status if status is not None else TaskStatus.BACKLOG,
        )
        result = tasks.create(session, caller, task_in)
    except (HTTPException, Refusal) as exc:
        raise refusal(exc) from exc

    [public] = task_publics(
        session, [result.task], projects={result.task.id: result.project.id}
    )

    return public.model_dump(mode="json")
