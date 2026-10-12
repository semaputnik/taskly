"""
`comment_task` (spec #247, #258): leave a note on a task, where the owner
will read it.

Built on `app.api.routes.comments.create_comment` itself — the `add_comments`
grant, the archive and the scope refusals are all that route's rules, called
through to directly the same way `complete_task` (#257) calls it for its own
optional comment, rather than re-derived here. This tool's own job is only
the argument translation (a task by a full id or the short prefix a compact
line prints) and the description teaching the one rule an agent needs before
it writes: a bot user's comment is append-only, so there is no second call
that fixes it (FR-03.2, FR-08.10).
"""

from typing import Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context

from app.api.routes.comments import create_comment as _create_comment
from app.mcp.conventions import open_caller, refusal, resolve_task_id
from app.mcp.server import mcp_server
from app.models import CommentBody, CommentCreate, CommentPublic


@mcp_server.tool()
def comment_task(ctx: Context, task_id: str, body: CommentBody) -> dict[str, Any]:
    """
    Leave a comment on a task, as this bot user, where the user will read
    the reasoning behind a change.

    Append-only: once written, a bot user's comment can never be edited or
    deleted by anyone — not the owner, not this bot user itself, and not
    through any other tool here. Write it once, properly; a correction is a
    new comment that says what was wrong with the last one, not a second
    call that tries to fix it.

    Needs the `add_comments` grant, not `update_tasks` — a bot user can
    report on a task without being able to change it, and is refused by name
    without that grant. `body` is trimmed and refused if it comes out blank,
    and its length limit (10,000 characters) is declared in this tool's own
    argument schema, so an over-long one is refused before the call reaches
    the API at all.

    `task_id` takes a full id or the short prefix a compact line's own `id`
    prints. Returns the comment as recorded, with its author.
    """
    with open_caller(ctx) as (session, caller):
        try:
            resolved_id = resolve_task_id(session, caller, task_id)
            # `_create_comment` is typed `-> Any` (a FastAPI route function,
            # where that is how a `response_model` is declared); it always
            # actually returns a `CommentPublic`, the full record this tool
            # promises.
            comment: CommentPublic = _create_comment(
                session=session,
                caller=caller,
                task_id=resolved_id,
                comment_in=CommentCreate(body=body),
            )
        except HTTPException as exc:
            raise refusal(exc) from exc

    return comment.model_dump(mode="json")
