"""
`complete_task` (spec #247, #257): close a task.

Calls `app.tasks.complete` directly (#275, #279): the open-subtasks
directive, the next-occurrence spawn (FR-01.14, ADR-0001), and the archive,
scope and permission refusals are all that operation's own rules now, the
same ones a human's `PATCH .../tasks/{id}` with `status: done` goes through —
neither a route function nor a route-private constant is imported here any
more. This tool's own job is what is special about asking for this over MCP:
knowing before it even calls the operation whether there is anything left to
close, naming the open subtasks straight from the refusal's own payload
rather than finding them with a second query, reading the next occurrence
the operation already found rather than looking for it again, and recording
an optional comment as part of the same act — refused by its own grant
before anything closes, and aborting the whole act if it is, since the
comment is no longer a call this tool makes outside the operation's own
error handling.
"""

from typing import Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from sqlmodel import Session

from app import tasks
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller
from app.mcp.conventions import open_caller, refusal, refuse, resolve_task_id, short_id
from app.mcp.server import mcp_server
from app.models import CommentBody, SubtaskCompletion, TaskStatus, TaskUpdate
from app.read_models import task_publics
from app.refusals import Refusal, RefusalCode, TaskHasUncompletedSubtasks


@mcp_server.tool(
    annotations=ToolAnnotations(destructive_hint=True),
)
def complete_task(
    ctx: Context,
    task_id: str,
    subtasks: SubtaskCompletion | None = None,
    comment: CommentBody | None = None,
) -> dict[str, Any]:
    """
    Close a task: move it to `done` — its own tool rather than an argument
    to `update_task`, because of the two things that make closing unlike any
    other status change.

    A parent with open subtasks is refused until `subtasks` says what
    happens to them — `complete` closes them too, `leave_uncompleted` leaves
    each in the open status it had — and the refusal names them, by id and
    title, so the answer can be given without a separate call to see what is
    in the way (FR-02.5–FR-02.7). `subtasks` sent on a call that closes
    nothing — the task is already done — is refused instead: there is
    nothing left for it to say.

    Closing the open occurrence of a recurring task creates the next one
    (FR-01.14), and this call reports its id and due date, so an agent is
    never unaware that a new task appeared; the due date comes from the
    series' own schedule (FR-01.15), not from when this call happened to
    run. A task that is already done is left exactly as it is and reported
    as such (`already_done`) rather than as an error.

    `comment` records a note on the task as this bot user's, in the same
    call (FR-03.1) — append-only, like every comment a bot user writes
    (FR-08.10). It needs the `add_comments` grant, checked and refused by
    name before anything closes, whether or not there turns out to be
    anything to close.

    `task_id` takes a full id or the short prefix a compact line's own `id`
    prints. Returns the closed task in full, alongside `next_occurrence`
    when closing created one.
    """
    with open_caller(ctx) as (session, caller):
        return complete_task_body(
            session, caller, task_id=task_id, subtasks=subtasks, comment=comment
        )


def complete_task_body(
    session: Session,
    caller: Caller,
    *,
    task_id: str,
    subtasks: SubtaskCompletion | None = None,
    comment: CommentBody | None = None,
) -> dict[str, Any]:
    """`complete_task`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    try:
        resolved_id = resolve_task_id(session, caller, task_id)
        resolved = access.get_task(session, caller, resolved_id, TaskAction.UPDATE)
    except HTTPException as exc:
        raise refusal(exc) from exc

    task = resolved.task
    if task.status is TaskStatus.DONE and subtasks is not None:
        refuse(
            "invalid_argument",
            f"“{task.title}” is already done. `subtasks` only applies "
            "to a call that closes something.",
        )

    task_in = TaskUpdate(status=TaskStatus.DONE, subtasks=subtasks)
    try:
        result = tasks.complete(
            session=session,
            caller=caller,
            task_id=resolved_id,
            task_in=task_in,
            comment=comment,
        )
    except Refusal as exc:
        if exc.code is not RefusalCode.TASK_HAS_UNCOMPLETED_SUBTASKS:
            raise refusal(exc) from exc
        assert isinstance(exc.payload, TaskHasUncompletedSubtasks)
        open_subtasks = exc.payload.subtasks
        listed = "; ".join(f"{short_id(t.id)} “{t.title}”" for t in open_subtasks)
        count = len(open_subtasks)
        refuse(
            exc.code,
            f"“{task.title}” has {count} open subtask{'' if count == 1 else 's'}: "
            f'{listed}. Send `subtasks: "complete"` to close them too, or '
            f'`subtasks: "leave_uncompleted"` to leave each where it is.',
        )
    except HTTPException as exc:
        raise refusal(exc) from exc

    [public] = task_publics(
        session, [result.task], projects={result.task.id: resolved.project.id}
    )
    result_dict = public.model_dump(mode="json")
    if result.already_done:
        result_dict["already_done"] = True
    elif result.next_occurrence is not None:
        successor = result.next_occurrence
        result_dict["next_occurrence"] = {
            "id": short_id(successor.id),
            "due_date": successor.due_date.isoformat()
            if successor.due_date is not None
            else None,
        }

    return result_dict
