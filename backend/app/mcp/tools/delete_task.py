"""
`delete_task` (spec #247, #258): take a task down on purpose, subtree
included.

Built on `app.api.routes.tasks.delete_task` itself — the `delete_tasks`
grant, the archive and scope refusals, the cascade-confirmation rule, and the
one-event-per-deletion recording (`app.deletions.delete_task`) are all that
route's rules, called through to directly the same way `complete_task`
(#257) calls `app.api.routes.tasks.update_task`. This tool's own job is
naming the subtasks a bare confirmation would take down, in the refusal,
since nothing else about this call would have shown the subtree first — the
same thing `complete_task` does for the open ones it refuses over, except a
delete cascades over every live descendant whatever its status, so
`crud.open_subtasks` (built for that other refusal) is the wrong read here;
`crud.subtasks` reads the whole subtree instead (see its own docstring).
"""

from collections.abc import Mapping
from typing import Any, NoReturn

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from sqlmodel import Session

from app import crud
from app.api import access
from app.api.access import TaskAction
from app.api.routes.tasks import HAS_SUBTASKS_CODE
from app.api.routes.tasks import delete_task as _delete_task
from app.mcp.conventions import open_caller, refusal, refuse, resolve_task_id, short_id
from app.mcp.server import mcp_server
from app.models import Task


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
        try:
            resolved_id = resolve_task_id(session, caller, task_id)
            # Fetched ahead of the route's own call so a refusal over its
            # subtasks has the task to name them from; the access decision
            # itself is still the route's a moment later.
            task = access.get_task(session, caller, resolved_id, TaskAction.DELETE).task
        except HTTPException as exc:
            raise refusal(exc) from exc

        try:
            _delete_task(
                session=session,
                caller=caller,
                task_id=resolved_id,
                delete_subtasks=delete_subtasks,
            )
        except HTTPException as exc:
            _refuse_has_subtasks(session, task, exc)

        # Built before the session closes: `deletions.delete_task` committed
        # above, which expires every attribute SQLAlchemy would otherwise
        # have to refresh from a now-closed session.
        result = {"id": short_id(resolved_id), "title": task.title, "deleted": True}

    return result


def _refuse_has_subtasks(session: Session, task: Task, exc: HTTPException) -> NoReturn:
    """
    `app.api.routes.tasks.delete_task`'s own refusal (FR-01.12) only says
    subtasks are in the way; this names them, by id and title, since nothing
    else about this call would have shown the subtree first.
    """
    detail = exc.detail
    if not isinstance(detail, Mapping) or detail.get("code") != HAS_SUBTASKS_CODE:
        raise refusal(exc) from exc

    descendants = crud.subtasks(session=session, task=task)
    listed = "; ".join(f"{short_id(t.id)} “{t.title}”" for t in descendants)
    count = len(descendants)
    refuse(
        HAS_SUBTASKS_CODE,
        f"“{task.title}” has {count} subtask{'' if count == 1 else 's'}, which "
        f"would be deleted with it: {listed}. Send `delete_subtasks: true` to "
        "confirm.",
    )
