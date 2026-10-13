"""
`update_task` (spec #247, #256): change a task's fields, move it between open
statuses or projects, hand it over, or clear a field.

Calls `app.tasks.update` directly (#275, #282): the subtasks directive, the
due-date scope, the superseded-occurrence refusal, the subtask-project rule,
and the archive and scope checks are all that operation's own rules now, the
same ones a human's `PATCH /tasks/{id}` goes through — neither a route
function nor a route-private constant is imported here any more. This tool's
own job is only to translate its MCP-style arguments (a project by name or
id, an assignee as `self`, `owner` or an id, a due date read by
`app.mcp.conventions.resolve_date`, an explicit `clear` naming the fields to
empty) into the `TaskUpdate` that operation already takes, and to refuse
`status: done` itself before the operation is ever called, pointing at
`complete_task` — so `update` never delegates to `complete` from here.
"""

from typing import Annotated, Any, Literal

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
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
    DueDateScope,
    TagName,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)
from app.read_models import task_publics
from app.refusals import Refusal

# What `clear` may name: every field a task can be emptied of. `title` and
# `status` cannot be (a task always has both; emptying either would reach the
# database as a value it refuses), `project` cannot either (a task must
# belong to one), and `tags` already has its own way to go empty — sending it
# as `[]` — so none of the four joins this list.
ClearableField = Literal["description", "due_date", "priority", "assignee"]


@mcp_server.tool(
    annotations=ToolAnnotations(idempotent_hint=True),
)
def update_task(
    ctx: Context,
    task_id: str,
    title: Annotated[str, Field(max_length=255)] | None = None,
    description: Annotated[str, Field(max_length=2000)] | None = None,
    project: str | None = None,
    priority: TaskPriority | None = None,
    due_date: str | None = None,
    due_date_scope: DueDateScope | None = None,
    assignee: str | None = None,
    status: TaskStatus | None = None,
    tags: list[TagName] | None = None,
    clear: list[ClearableField] | None = None,
) -> dict[str, Any]:
    """
    Change a task that already exists: retitle it, rewrite its description,
    move it between open statuses or into another project, put it on
    someone, replace its tags, or move its due date — one call, any
    combination of fields, each one left alone by leaving its argument out.

    Hand finished work over this way: move `status` to `review` and set
    `assignee` to `owner` in the same call, with a comment (`comment_task`)
    saying what was done. The two are independent — nothing moves a task
    onto the owner because it entered Review, and a task left on the bot
    that did the work does not reach the owner's dashboard. There is no
    separate hand-over tool; this is how one is done.

    `status` only reaches the open statuses here (`backlog`, `todo`,
    `in_progress`, `waiting`, `review`); moving a task to `done` is refused,
    pointing at `complete_task`, which is also where the question about open
    subtasks belongs. Moving between open statuses never touches a task's
    subtasks. Reopening an earlier occurrence of a recurring series is
    refused, naming the latest occurrence, which is the only one that can be.

    `project` takes a name, case-insensitively, or an id, and moves the task
    there; moving into a project outside this bot user's scope, or out of
    one, is refused by name. A subtask cannot be moved between projects at
    all — it follows the task at the top of its tree, so send `project` to
    that task instead.

    `assignee` takes `self` (this bot user), `owner` (the human who owns
    this account), or a bot user's id — never another user's, and never the
    reporter, which no argument here reaches. A deleted bot user keeps the
    tasks already on it but takes no new one.

    `tags` replaces the task's tags wholesale, the same way the REST API
    does: sending some tags drops every tag not sent, and sending `[]`
    clears them all. A name that is not a tag of this owner's yet needs the
    `create_tags` grant, and the refusal names which of the sent names were
    new.

    `due_date` takes an ISO date, `today`, `tomorrow`, or `+<count>d`, read
    against the server's own date. Moving the due date of the open
    occurrence of a recurring task needs `due_date_scope` to say whether the
    change is `this_occurrence` only or `this_and_following` ones too; a
    request that moves such a date without one is refused with the
    difference explained, and a `due_date_scope` sent where there is no
    series to reschedule is refused as well.

    `description`, `due_date`, `priority` and `assignee` are the only fields
    an explicit `clear` can empty, by naming them; sending one of them a
    value and naming it in `clear` at once is refused. Nothing else here can
    be emptied this way: a task always has a title, a status, and a project,
    and `tags` already goes empty by being sent as `[]`.

    Returns the updated task in full.
    """
    with open_caller(ctx) as (session, caller):
        return update_task_body(
            session,
            caller,
            task_id=task_id,
            title=title,
            description=description,
            project=project,
            priority=priority,
            due_date=due_date,
            due_date_scope=due_date_scope,
            assignee=assignee,
            status=status,
            tags=tags,
            clear=clear,
        )


def update_task_body(
    session: Session,
    caller: Caller,
    *,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    project: str | None = None,
    priority: TaskPriority | None = None,
    due_date: str | None = None,
    due_date_scope: DueDateScope | None = None,
    assignee: str | None = None,
    status: TaskStatus | None = None,
    tags: list[TagName] | None = None,
    clear: list[ClearableField] | None = None,
) -> dict[str, Any]:
    """`update_task`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    cleared = set(clear or [])
    _refuse_conflicting_clears(
        cleared,
        description=description,
        due_date=due_date,
        priority=priority,
        assignee=assignee,
    )
    if status is TaskStatus.DONE:
        refuse(
            "invalid_argument",
            "update_task does not move a task to done. Use complete_task to "
            "close it — that is where the question about open subtasks "
            "belongs.",
        )

    try:
        resolved_id = resolve_task_id(session, caller, task_id)
        fields: dict[str, Any] = {}
        if title is not None:
            fields["title"] = title
        if description is not None:
            fields["description"] = description
        elif "description" in cleared:
            fields["description"] = None
        if due_date is not None:
            fields["due_date"] = resolve_date(due_date)
        elif "due_date" in cleared:
            fields["due_date"] = None
        if priority is not None:
            fields["priority"] = priority
        elif "priority" in cleared:
            fields["priority"] = None
        if project is not None:
            fields["project_id"] = resolve_project_id(session, caller, project)
        if assignee is not None:
            fields["assignee_id"] = resolve_assignee(caller, assignee)
        elif "assignee" in cleared:
            fields["assignee_id"] = None
        if status is not None:
            fields["status"] = status
        if tags is not None:
            fields["tags"] = tags
        if due_date_scope is not None:
            fields["due_date_scope"] = due_date_scope

        task_in = TaskUpdate(**fields)
        result = tasks.update(
            session=session, caller=caller, task_id=resolved_id, task_in=task_in
        )
    except (HTTPException, Refusal) as exc:
        raise refusal(exc) from exc

    # `status: done` is refused above, before the operation is ever called,
    # so `update` never delegates to `complete` on this path.
    assert isinstance(result, tasks.UpdateResult)
    [public] = task_publics(
        session,
        [result.task],
        projects={result.task.id: result.project.id},
        recurrences={result.task.id: result.recurrence},
    )

    return public.model_dump(mode="json")


def _refuse_conflicting_clears(
    cleared: set[ClearableField],
    *,
    description: str | None,
    due_date: str | None,
    priority: TaskPriority | None,
    assignee: str | None,
) -> None:
    """
    A field sent a value and named in `clear` at once asks two things of the
    same field; refused rather than picking one silently.
    """
    sent = {
        "description": description is not None,
        "due_date": due_date is not None,
        "priority": priority is not None,
        "assignee": assignee is not None,
    }
    conflicts = sorted(name for name in cleared if sent.get(name))
    if conflicts:
        named = ", ".join(f"`{name}`" for name in conflicts)
        refuse(
            "invalid_argument",
            f"{named} {'were' if len(conflicts) > 1 else 'was'} sent a value "
            f"and listed in `clear`. Send a value to set it, or list it in "
            f"`clear` to empty it — not both.",
        )
