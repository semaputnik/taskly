"""
`get_task` (spec #247, #254): one task read whole — its full record (F-01,
F-02), and, only when asked for, its subtasks, comments and attachment names
(F-02, F-03, F-04) — so a caller that wants the task alone pays for the task
alone. Built on `app.read_models.task_publics`, the same read model
`app.api.routes.tasks.read_task` uses, rather than a second description of a
task's shape, and on `app.mcp.conventions` for everything else.
"""

from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from sqlmodel import Session

from app import crud
from app.api import access
from app.api.access import TaskAction
from app.mcp.conventions import open_caller, refusal, render_task_rows, resolve_task_id
from app.mcp.server import mcp_server
from app.models import BotUserRef, Comment, TaskQuery
from app.read_models import task_publics


@mcp_server.tool(
    annotations=ToolAnnotations(read_only_hint=True),
)
def get_task(
    ctx: Context,
    task_id: str,
    include_subtasks: bool = False,
    include_comments: bool = False,
    include_attachments: bool = False,
) -> dict[str, Any]:
    """
    Read one task in full: title, description, status, priority, due date,
    project, tags, assignee, reporter, recurrence, when it was filed, and its
    subtask counts — the same record `GET /tasks/{id}` returns. A subtask
    reports the project of its root task (FR-02.4); a task in Review that a
    bot user handed over reports the hand-over (ADR-0008).

    `task_id` takes a full id or the short prefix a compact line's own `id`
    prints.

    Its subtasks, comments and attachments cost nothing unless asked for:
    `include_subtasks` lists the direct subtasks as compact lines, the same
    shape `search_tasks` returns; `include_comments` lists the task's
    comments oldest first, each with its author ("owner", or a bot user by
    name) and when it was written; `include_attachments` lists the task's
    attachments by name and size, never their bytes.
    """
    with open_caller(ctx) as (session, caller):
        try:
            resolved_id = resolve_task_id(session, caller, task_id)
            resolved = access.get_task(session, caller, resolved_id, TaskAction.READ)
        except HTTPException as exc:
            raise refusal(exc) from exc

        [public] = task_publics(
            session, [resolved.task], projects={resolved.task.id: resolved.project.id}
        )
        result = public.model_dump(mode="json")

        if include_subtasks:
            subtasks, _ = crud.get_tasks(
                session=session,
                owner_id=caller.owner_id,
                query=TaskQuery(parent_id=resolved_id),
                project_ids=caller.project_ids if caller.bot else None,
            )
            result["subtasks"] = render_task_rows(session, subtasks, caller.owner_id)

        if include_comments:
            comments, _ = crud.get_comments(session=session, task_id=resolved_id)
            result["comments"] = _comment_rows(session, comments)

        if include_attachments:
            attachments, _ = crud.get_attachments(session=session, task_id=resolved_id)
            result["attachments"] = [
                {"filename": attachment.filename, "size": attachment.size}
                for attachment in attachments
            ]

    return result


def _comment_rows(session: Session, comments: Sequence[Comment]) -> list[dict[str, Any]]:
    """
    A task's comments as spec #254 asks for them: oldest first (already
    `crud.get_comments`' own order), each with its author — "owner", or a bot
    user by name, "(deleted)" appended if it no longer exists (FR-08.21) —
    and when it was written.
    """
    bots = crud.get_bot_user_refs(
        session=session,
        bot_user_ids=[comment.author_bot_user_id for comment in comments],
    )
    rows = []
    for comment in comments:
        bot = bots.get(comment.author_bot_user_id) if comment.author_bot_user_id else None
        rows.append(
            {
                "body": comment.body,
                "author": _author(bot),
                "created_at": comment.created_at.isoformat()
                if comment.created_at is not None
                else None,
            }
        )
    return rows


def _author(bot: BotUserRef | None) -> str:
    if bot is None:
        return "owner"
    return f"{bot.name} (deleted)" if bot.deleted else bot.name
