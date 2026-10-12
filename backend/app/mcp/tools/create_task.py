"""
`create_task` (spec #247, #255): file a task, a subtask or a recurring one.

Built on `app.api.routes.tasks.create_task` itself — the Inbox default for a
task created without a project, a subtask's own project, the assignee, the
reporter, the tag grant and the recurrence checks are all that route's rules,
called through to directly the same way `app.mcp.tools.whoami` calls
`read_caller` — rather than re-derived here. This tool's own job is only to
translate its MCP-style arguments (a project by name or id, a parent task by
a full id or the short prefix a compact line prints, an assignee as `self`,
`owner` or an id, a due date read by `app.mcp.conventions.resolve_date`) into
the `TaskCreate` that route already takes.
"""

import uuid
from typing import Annotated, Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from pydantic import Field

from app.api.deps import Caller
from app.api.routes.tasks import create_task as _create_task
from app.mcp.conventions import (
    open_caller,
    refusal,
    refuse,
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
    TaskPublic,
    TaskStatus,
)


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
    if parent_task_id is not None and project is not None:
        refuse(
            "invalid_argument",
            "A subtask belongs to the project of its parent; name no project for it.",
        )

    with open_caller(ctx) as (session, caller):
        try:
            project_id = (
                resolve_project_id(session, caller, project)
                if project is not None
                else None
            )
            parent_id = (
                resolve_task_id(session, caller, parent_task_id)
                if parent_task_id is not None
                else None
            )
            due = resolve_date(due_date) if due_date is not None else None
            assignee_id = _resolve_assignee(caller, assignee)

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
            # `_create_task` is typed `-> Any` (a FastAPI route function,
            # where that is how a `response_model` is declared); it always
            # actually returns a `TaskPublic`, the full record this tool
            # promises.
            public: TaskPublic = _create_task(
                session=session, caller=caller, task_in=task_in
            )
        except HTTPException as exc:
            raise refusal(exc) from exc

    return public.model_dump(mode="json")


def _resolve_assignee(caller: Caller, raw: str | None) -> uuid.UUID | None:
    """
    `assignee` as `TaskCreate.assignee_id` wants it: `self` is the
    connecting bot's own id, `owner` is the human owner's, anything else is
    read as a bot user's id outright.
    `app.api.routes.tasks._resolve_assignee` still makes the real decision
    (not one of the owner's, deleted, nonexistent) a moment later.
    """
    if raw is None:
        return None
    if raw == "self":
        assert caller.bot is not None, "an MCP caller is always a bot"
        return caller.bot.id
    if raw == "owner":
        return caller.owner_id
    try:
        return uuid.UUID(raw)
    except ValueError:
        refuse(
            "invalid_argument",
            f"“{raw}” is not “self”, “owner”, or a bot user id.",
        )
