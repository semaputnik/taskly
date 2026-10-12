"""
`complete_task` (spec #247, #257): close a task.

Built on `app.api.routes.tasks.update_task` itself — the open-subtasks
directive, the next-occurrence spawn (FR-01.14, ADR-0001) and the archive,
scope and permission refusals are all that route's rules, called through to
directly the same way `update_task` (#256) calls it. This tool's own job is
the three things closing needs that no other status change does: naming the
open subtasks in the refusal rather than just saying there are some, finding
and reporting the occurrence that closing one creates (the route's own
return value never carried it), and recording an optional comment (through
`app.api.routes.comments.create_comment`, the same route a hand-over's own
comment goes through) in the same call — refused by its own grant before
anything closes, never after.
"""

from collections.abc import Mapping
from typing import Any, NoReturn

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from sqlalchemy import not_
from sqlmodel import Session, col, select

from app import crud
from app.api import access
from app.api.access import TaskAction
from app.api.routes.comments import create_comment as _create_comment
from app.api.routes.tasks import OPEN_SUBTASKS_CODE
from app.api.routes.tasks import update_task as _update_task
from app.mcp.conventions import open_caller, refusal, refuse, resolve_task_id, short_id
from app.mcp.server import mcp_server
from app.models import (
    CommentBody,
    CommentCreate,
    SubtaskCompletion,
    Task,
    TaskPublic,
    TaskStatus,
    TaskUpdate,
)
from app.read_models import task_publics


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
        try:
            resolved_id = resolve_task_id(session, caller, task_id)
            # The comment grant is its own check, ahead of anything that
            # closes, so a call that cannot leave its note closes nothing
            # either — never refused only after the fact.
            if comment is not None:
                access.get_task(session, caller, resolved_id, TaskAction.COMMENT)
            resolved = access.get_task(session, caller, resolved_id, TaskAction.UPDATE)
        except HTTPException as exc:
            raise refusal(exc) from exc

        task = resolved.task
        already_done = task.status is TaskStatus.DONE

        if already_done and subtasks is not None:
            refuse(
                "invalid_argument",
                f"“{task.title}” is already done. `subtasks` only applies "
                "to a call that closes something.",
            )

        public: TaskPublic
        if already_done:
            [public] = task_publics(
                session, [task], projects={task.id: resolved.project.id}
            )
        else:
            task_in = TaskUpdate(status=TaskStatus.DONE, subtasks=subtasks)
            try:
                # `_update_task` is typed `-> Any` (a FastAPI route
                # function, where that is how a `response_model` is
                # declared); it always actually returns a `TaskPublic`, the
                # full record this tool promises.
                public = _update_task(
                    session=session,
                    caller=caller,
                    task_id=resolved_id,
                    task_in=task_in,
                )
            except HTTPException as exc:
                _refuse_open_subtasks(session, task, exc)

        result = public.model_dump(mode="json")
        if already_done:
            result["already_done"] = True
        elif (occurrence := _next_occurrence(session, task)) is not None:
            result["next_occurrence"] = occurrence

        if comment is not None:
            _create_comment(
                session=session,
                caller=caller,
                task_id=resolved_id,
                comment_in=CommentCreate(body=comment),
            )

    return result


def _refuse_open_subtasks(session: Session, task: Task, exc: HTTPException) -> NoReturn:
    """
    `update_task`'s own open-subtasks refusal (FR-02.6) only says there is
    something in the way; `complete_task` names it, by id and title, since
    nothing else about this call would have shown the subtree first.
    """
    detail = exc.detail
    if not isinstance(detail, Mapping) or detail.get("code") != OPEN_SUBTASKS_CODE:
        raise refusal(exc) from exc

    subtasks = crud.open_subtasks(session=session, task=task)
    listed = "; ".join(f"{short_id(t.id)} “{t.title}”" for t in subtasks)
    count = len(subtasks)
    refuse(
        OPEN_SUBTASKS_CODE,
        f"“{task.title}” has {count} open subtask{'' if count == 1 else 's'}: "
        f'{listed}. Send `subtasks: "complete"` to close them too, or '
        f'`subtasks: "leave_uncompleted"` to leave each where it is.',
    )


def _next_occurrence(session: Session, closed: Task) -> dict[str, Any] | None:
    """
    The occurrence closing `closed` just created, if its series had one to
    create (FR-01.14) — the one open occurrence left in that series
    (FR-01.16), read back here since `update_task`'s own return value never
    carried it.
    """
    if closed.series_id is None:
        return None
    successor = session.exec(
        select(Task).where(
            Task.series_id == closed.series_id,
            not_(col(Task.status) == TaskStatus.DONE),
        )
    ).first()
    if successor is None:
        return None
    return {
        "id": short_id(successor.id),
        "due_date": successor.due_date.isoformat()
        if successor.due_date is not None
        else None,
    }
