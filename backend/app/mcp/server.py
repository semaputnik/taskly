"""
The one `MCPServer` instance every tool registers on (spec #252, #253).

Kept apart from `app.mcp.gateway` (the ASGI wiring) and `app.mcp.tools` (the
tools themselves) so that neither has to import the other to reach the
server: a tool module imports `mcp_server` from here to decorate itself with
`@mcp_server.tool(...)`, and the gateway imports it to build the session
manager `run()` serves. `app.mcp.conventions` holds the argument/output/
refusal rules every tool follows; this module holds only the server and the
one extension that enforces a rule no single tool can enforce on its own.
"""

from collections.abc import Mapping
from typing import Any

from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import Extension, MCPServer
from mcp.types import CallToolRequestParams, CallToolResult, TextContent


class _RefuseNullArguments(Extension):
    """
    "Absent means leave alone, null means clear" is a distinction a model and
    a transport both lose (spec #247): a client that means to omit an
    argument can still serialise it as JSON `null`, and nothing downstream
    tells the two apart once a tool's own parameter has a default. Refusing
    every `null` here, once, for every tool's arguments, is what lets the
    `clear` convention (a later ticket) mean something — the only way a field
    is ever emptied is by naming it in `clear`, never by sending it as null.

    Implemented as a `tools/call` interceptor (SEP-2133) rather than inside
    each tool: by the time a tool function is actually called, the SDK's own
    argument validation has already bound each JSON value to a Python
    parameter, and a field typed `X | None` cannot tell "sent as null" apart
    from "defaulted to None" any more either. Intercepting the raw
    `arguments` mapping, before that binding happens, is the only point left
    that still can.
    """

    identifier = "app.taskly/arguments"

    async def intercept_tool_call(
        self,
        params: CallToolRequestParams,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        nulls = _null_argument_names(params.arguments)
        if not nulls:
            return await call_next(ctx)
        named = ", ".join(f"`{name}`" for name in nulls)
        plural = len(nulls) > 1
        message = (
            f"{named} {'were' if plural else 'was'} sent as null. Omit "
            f"{'them' if plural else 'it'} to leave {'them' if plural else 'it'} "
            "unset, or send a real value."
        )
        return CallToolResult(
            content=[TextContent(type="text", text=f"invalid_argument: {message}")],
            is_error=True,
        )


def _null_argument_names(arguments: Mapping[str, Any] | None) -> list[str]:
    if not arguments:
        return []
    return sorted(name for name, value in arguments.items() if value is None)


mcp_server = MCPServer(
    name="taskly",
    instructions=(
        "Taskly, reached as the bot user whose token authorised this "
        "connection. Call `whoami` first, every session: it names the "
        "actor, its owner, the scope's projects (the Inbox marked), "
        "exactly its grants, and the server's own current date — the "
        "caller's own clock is not this installation's."
    ),
    extensions=[_RefuseNullArguments()],
)
