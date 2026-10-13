"""
Calling an MCP tool's body directly (#302): the "half adapter" the issue
describes, alongside the decorated tool function itself — a session and a
`Caller`, with no protocol in between.

Fixtures are still built through the REST API (`tests.utils.accounts`), the
same way every other test here builds them: that scaffolding was never the
cost the ticket is about. What a body-level test skips is the three-request
handshake (`initialize`, `notifications/initialized`, `tools/call`)
`tests.utils.mcp.call_tool` drives for a protocol test — `caller_for` turns a
bot user's token into the exact `Caller` a tool's own `open_caller` would
have resolved, through the same `get_mcp_caller` (ADR-0012), in one direct
call.
"""

from sqlmodel import Session

from app.api.deps import Caller, get_mcp_caller


def caller_for(session: Session, headers: dict[str, str]) -> Caller:
    """
    The `Caller` a bot user's own headers (`tests.utils.mcp.bot_headers`, or
    `tests.utils.accounts.token_headers`) resolve to — read straight off the
    bearer token, the same way a tool's own `open_caller` reads it from the
    MCP request, minus the request.
    """
    token = headers["Authorization"].removeprefix("Bearer ")
    return get_mcp_caller(session, token)
