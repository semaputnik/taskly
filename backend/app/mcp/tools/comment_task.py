"""
`comment_task` (spec #247, #258): leave a note on a task, where the owner
will read it.

Calls `app.comments.comment` directly (#275, #281): the `add_comments`
grant, the archive and the scope refusals are all that operation's own
rules now, the same ones `complete_task` (#257) already reaches for its own
optional comment and a human's `POST /tasks/{id}/comments` goes through —
neither a route function nor a route-private constant is imported here any
more. This tool's own job is only the argument translation (a task by a
full id or the short prefix a compact line prints) and the description
teaching the one rule an agent needs before it writes: a bot user's comment
is append-only, so there is no second call that fixes it (FR-03.2, FR-08.10).
"""

from typing import Any

from mcp.server.mcpserver import Context
from sqlmodel import Session

from app import comments
from app.api.deps import Caller
from app.mcp.conventions import open_caller, refusal, resolve_task_id
from app.mcp.server import mcp_server
from app.models import BotUserRef, CommentBody, CommentCreate, CommentPublic
from app.refusals import Refusal


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
        return comment_task_body(session, caller, task_id=task_id, body=body)


def comment_task_body(
    session: Session, caller: Caller, *, task_id: str, body: CommentBody
) -> dict[str, Any]:
    """`comment_task`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    try:
        resolved_id = resolve_task_id(session, caller, task_id)
        comment_row = comments.comment(
            session, caller, resolved_id, CommentCreate(body=body)
        )
    except Refusal as exc:
        raise refusal(exc) from exc

    # The author is always this call's own bot user — an MCP caller is
    # always a bot (ADR-0012) — already loaded on `caller`, so there is no
    # need to query it back the way `app.api.routes.comments._public` does
    # for a reader that does not already know who wrote it.
    assert caller.bot is not None, "an MCP caller is always a bot"
    author = BotUserRef(
        id=caller.bot.id,
        name=caller.bot.name,
        deleted=caller.bot.deleted_at is not None,
    )
    public = CommentPublic.model_validate(
        comment_row, update={"author_bot_user": author}
    )

    return public.model_dump(mode="json")
