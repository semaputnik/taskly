"""`whoami`, the first tool (spec #252): answers exactly what `GET /caller` answers (spec #245, #249), read over MCP instead of REST."""

from typing import Any

from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from app.api.routes.caller import read_caller
from app.mcp.conventions import open_caller
from app.mcp.server import mcp_server
from app.models import CallerPublic


@mcp_server.tool(
    annotations=ToolAnnotations(read_only_hint=True),
)
def whoami(ctx: Context) -> dict[str, Any]:
    """
    Who this connection is: the actor and its owner, the scope's projects
    (Inbox marked) with their open-task counts, exactly its grants, and
    today's server date. Answers exactly what `GET /caller` answers (spec
    #245) — the two share `read_caller` rather than keeping two descriptions
    of a caller in step by hand.
    """
    with open_caller(ctx) as (session, caller):
        # `read_caller` is typed `-> Any` (it is a FastAPI route function,
        # where that is how a `response_model` is declared); it always
        # actually returns a `CallerPublic`.
        result: CallerPublic = read_caller(session, caller)
    return result.model_dump(mode="json")
