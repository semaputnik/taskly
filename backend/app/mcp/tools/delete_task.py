"""
`delete_task` (spec #247, #258): take a task down on purpose, subtree
included.

Calls `app.tasks.delete` directly (#275, #282): the `delete_tasks` grant, the
archive and scope refusals, the cascade-confirmation rule, and the
one-event-per-deletion recording (`app.deletions.delete_task`) are all that
operation's own rules now, the same ones a human's `DELETE /tasks/{id}` goes
through — neither a route function nor a route-private constant is imported
here any more. This tool's own job is naming the subtasks a bare confirmation
would take down, in the refusal, since nothing else about this call would
have shown the subtree first — read straight off the refusal's own payload
(`app.refusals.TaskHasSubtasks`), which carries the whole live subtree the
operation already queried, so this tool's own subtree query is gone.
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
from app.refusals import Refusal, RefusalCode, TaskHasSubtasks


@mcp_server.tool(
    annotations=ToolAnnotations(destructive_hint=True),
)
def delete_task(
    ctx: Context, task_id: str, delete_subtasks: bool = False
) -> dict[str, Any]:
    """
    Delete a task, and its subtasks with it.

    The row is marked deleted, not removed, so the delete is recorded in the
    owner's activity log and restorable from there — by the owner, and only
    the owner. This tool has no undo: once this call succeeds, this bot user
    cannot bring the task back. Ask the user before doing this.

    A task with subtasks is refused until `delete_subtasks` confirms the
    whole subtree goes too; the refusal names every subtask that would go
    down with it, by id and title, whatever its own status — the cascade
    takes a done subtask along with an open one. The delete is then recorded
    as one event covering the whole subtree, restorable as the one act it
    was.

    Needs the `delete_tasks` grant, refused by name without it; the archive
    and the scope are refused the way every other tool here refuses them.

    `task_id` takes a full id or the short prefix a compact line's own `id`
    prints.
    """
    with open_caller(ctx) as (session, caller):
        return delete_task_body(
            session, caller, task_id=task_id, delete_subtasks=delete_subtasks
        )


def delete_task_body(
    session: Session, caller: Caller, *, task_id: str, delete_subtasks: bool = False
) -> dict[str, Any]:
    """`delete_task`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    try:
        resolved_id = resolve_task_id(session, caller, task_id)
        # Fetched ahead of the operation's own call so a refusal over its
        # subtasks has the task to name them from; the access decision
        # itself is still the operation's a moment later.
        task = access.get_task(session, caller, resolved_id, TaskAction.DELETE).task
    except HTTPException as exc:
        raise refusal(exc) from exc

    try:
        tasks.delete(
            session=session,
            caller=caller,
            task_id=resolved_id,
            delete_subtasks=delete_subtasks,
        )
    except Refusal as exc:
        if exc.code is not RefusalCode.TASK_HAS_SUBTASKS:
            raise refusal(exc) from exc
        assert isinstance(exc.payload, TaskHasSubtasks)
        descendants = exc.payload.subtasks
        listed = "; ".join(f"{short_id(t.id)} “{t.title}”" for t in descendants)
        count = len(descendants)
        refuse(
            exc.code,
            f"“{task.title}” has {count} subtask{'' if count == 1 else 's'}, "
            f"which would be deleted with it: {listed}. Send "
            "`delete_subtasks: true` to confirm.",
        )
    except HTTPException as exc:
        raise refusal(exc) from exc

    # `task` was loaded before the delete and the delete never renames a
    # task, so its title is read here unchanged rather than queried back —
    # `tasks.delete`'s own `UnitOfWork` (#284) has by now committed the
    # deletion, but nothing about reading an already-loaded attribute
    # depends on that.
    return {"id": short_id(resolved_id), "title": task.title, "deleted": True}
