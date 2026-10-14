"""
`list_tags` (spec #247, #254): the owner's whole tag vocabulary (FR-01.26),
read over MCP so an agent applies an existing tag instead of inventing a
spelling. Tags belong to the owner, not to a project (ADR-0003), so unlike
every other tool here this one is never narrowed by the caller's own scope —
and, for the same reason, it is the one tool that reads straight through
`crud.get_tags` rather than resolving anything through `app.api.access`,
which has nothing to say about a tag.

Its envelope was its own small copy of the shape `search_tasks` already had,
until `search_activity` (#259) needed a third one: `list_result` is
generalised there to take the row's own key (`"tags"` here), and this module
moved onto it rather than keep its own.
"""

from typing import Annotated, Any

from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlmodel import Session

from app import crud
from app.api.deps import Caller
from app.mcp.conventions import list_result, open_caller
from app.mcp.server import mcp_server


@mcp_server.tool(
    annotations=ToolAnnotations(read_only_hint=True),
)
def list_tags(
    ctx: Context,
    q: str | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    """
    The owner's tags, each with how many tasks carry it, so an agent applies
    a tag that already exists rather than minting a new spelling of one. `q`
    matches anywhere in a tag's name, ignoring case.

    Never narrowed by this bot user's own scope: tags belong to the owner,
    not to a project (ADR-0003), so every bot user reading them sees the same
    vocabulary, whatever projects it can itself reach.

    `task_count` is a tag's live tasks; `archived_task_count` is those
    archived with their project, counted but out of a bot user's reach.
    """
    with open_caller(ctx) as (session, caller):
        return list_tags_body(session, caller, q=q, limit=limit)


def list_tags_body(
    session: Session, caller: Caller, *, q: str | None, limit: int
) -> dict[str, Any]:
    """`list_tags`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    tags, count = crud.get_tags(
        session=session,
        owner_id=caller.owner_id,
        contains=q,
        limit=limit,
        name_creators=False,
    )

    rows = [
        {
            "id": str(tag.id),
            "name": tag.name,
            "task_count": tag.task_count,
            "archived_task_count": tag.archived_task_count,
        }
        for tag in tags
    ]
    return list_result(
        rows, key="tags", count=count, narrow_with="q" if q is None else None
    )
