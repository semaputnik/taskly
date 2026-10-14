"""
The ASGI gateway at `/mcp` (spec #252, ADR-0012): the same Taskly a bot user
already reaches over the REST API, read by an agent as a small set of tools
instead of routes. Outside `app.api.main`'s versioned prefix: an MCP client
is not a REST API consumer, and has no `/api/v1` of its own to carry.

Authorisation is never reimplemented here. `get_mcp_caller`
(`app.api.deps`) is the same `_authenticate_bot` the REST API's `get_caller`
uses, so a human session, an unknown token, and a revoked, expired or deleted
bot user's token are each refused exactly as `/caller` refuses them (spec
#245, #249). `_BotGateway` below calls it once per HTTP request, before any
MCP message on that request is read, so `initialize` and `tools/list` are
refused the same as a `tools/call` would be; nothing it learns is cached —
every tool calls `get_mcp_caller` again, with its own session, through
`app.mcp.conventions.open_caller`, so a scope edited between two calls shows
in the second.

This module is wiring only: the ASGI boundary and `mount`/`run`. The server
instance every tool registers on lives in `app.mcp.server`; the rules a
tool's arguments, output and refusals follow live in `app.mcp.conventions`;
the tools themselves live in `app.mcp.tools`, one module per tool (or per
small group), imported by `app.mcp.tools`'s own `__init__` so each registers
itself with `@mcp_server.tool(...)` on import. A new tool adds a module
there and nothing here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from mcp.server.transport_security import TransportSecuritySettings
from sqlmodel import Session
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.api.deps import get_mcp_caller
from app.core.db import engine
from app.mcp import tools as _tools  # noqa: F401 — import registers every tool
from app.mcp.conventions import bearer_token
from app.mcp.server import mcp_server

MCP_PATH = "/mcp"


class _BotGateway:
    """
    The ASGI boundary at `/mcp`: resolves every request's bearer token with
    `get_mcp_caller` before any MCP message on it is processed (spec #252,
    #325).

    The server runs stateless (`stateless_http=True`, `run()` below):
    `StreamableHTTPSessionManager` never mints a session id and builds a
    fresh transport per request, so there is nothing here to remember
    between one request and the next. That is also why this class needs no
    per-process state of its own — every request stands on its own, resolved
    from its own bearer token, which is exactly what FR-07.7 already
    promised ("nothing about the caller is cached between calls") and what
    FR-07.8 now says plainly: there are no protocol sessions, so there is no
    session for one agent to continue as another's.

    An earlier version of this class kept a session-to-token binding
    (`_session_tokens`) across calls, which only ever worked within one
    worker process: the release image runs four (`backend/Dockerfile`), and
    the kernel spreads one session's requests across all of them, so a
    follow-up call landing on a different worker found a session the stateful
    SDK path had never minted there — "Session not found" roughly three
    calls in four (#325). Going stateless removes the session, and with it
    the binding that only ever protected one process's own memory of it.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # A route only ever receives the "http" scope type (routing for
        # "lifespan" and "websocket" happens above it); this app never opens
        # a websocket, so there is nothing else to branch on here. (The SSE
        # GET stream the stateful path used to serve is gone too — `mount`
        # below narrows the route to POST.)
        session_manager = mcp_server.session_manager
        headers = Headers(scope=scope)
        try:
            token = bearer_token(headers)
            with Session(engine) as session:
                get_mcp_caller(session, token)
        except HTTPException as exc:
            await _deny(scope, receive, send, exc.status_code, exc.detail)
            return

        await session_manager.handle_request(scope, receive, send)


_gateway = _BotGateway()


async def _deny(
    scope: Scope, receive: Receive, send: Send, status_code: int, detail: Any
) -> None:
    await JSONResponse({"detail": detail}, status_code=status_code)(
        scope, receive, send
    )


def mount(app: FastAPI) -> None:
    """
    Register `/mcp` on `app`'s own router, answering it directly rather than
    `Mount`ing `MCPServer.streamable_http_app()`'s Starlette app as a
    sub-app — that app registers one `Route("/mcp", ...)`, so mounting it at
    `/mcp` would ask a bare `/mcp` to redirect to `/mcp/` on every call (the
    inner route only matches with the extra segment); registering
    `_BotGateway` as an exact `Route` here does not.

    `_gateway` resolves `mcp_server.session_manager` itself, per request
    (see its docstring), so there is nothing to build yet here — `run()`
    below is what brings the session manager into being, when this app's
    lifespan starts.
    """
    app.add_route(
        MCP_PATH,
        # FastAPI's `add_route` is typed for a `Request -> Response`
        # function; Starlette's `Route`, which it delegates to, also
        # accepts a raw ASGI app (any non-function/method callable) and
        # runs it as one — confirmed empirically — which is what `_gateway`
        # is. The stub is narrower than the runtime behaviour it wraps.
        _gateway,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
        # POST only (#325): stateless mode answers `DELETE` with 405
        # ("Session termination not supported" — there is no session to
        # terminate) and a `GET` whose `Accept` includes `text/event-stream`
        # opens a standalone SSE stream that nothing ever writes to
        # (`can_send_request=False` in the SDK's stateless path) and holds
        # the connection open until the client disconnects. Neither method
        # does anything worth offering once there is no session behind it.
        methods=["POST"],
        include_in_schema=False,
    )


@asynccontextmanager
async def run() -> AsyncIterator[None]:
    """
    Run the MCP session manager for as long as `app` serves requests
    (`app.main.lifespan`), the way `StreamableHTTPSessionManager.run()` asks
    to be run.

    Built fresh here rather than once at import time: a process restart in
    production, or a new `TestClient(app)` context between test modules
    here, re-enters this every time, and a `StreamableHTTPSessionManager`
    refuses to be run a second time on the same instance — so each cycle
    gets its own.

    `MCPServer.streamable_http_app()` is the only way `MCPServer` builds a
    session manager at all; its returned Starlette app is never mounted (see
    `mount`) — only the side effect of its being built is wanted here.

    `stateless_http=True` (#325) is what actually fixes the production bug:
    the release image runs four workers (`backend/Dockerfile`) sharing one
    listening socket, and the stateful path (`stateless_http=False`, the
    SDK's own default) keeps each session in the memory of whichever worker
    handled `initialize` — a follow-up call landing on a different worker
    found a session that worker never minted, "Session not found" roughly
    three calls in four. Stateless mode creates a transport per request
    instead, never sets `Mcp-Session-Id`, and needs nothing shared between
    workers because there is nothing to share: every call still authenticates
    on its own bearer token (`_BotGateway`, FR-07.7), and nothing under
    `app/mcp/` sends a request or a notification to a client that a session
    would be needed to address.

    DNS-rebinding protection is off: it guards a `127.0.0.1`-bound dev server
    against a malicious page's background fetch finding it by name, which
    does not apply to a server reached over a real hostname through TLS,
    whose only credential — a bearer token — a cross-origin page cannot
    attach without the CORS permission `CORSMiddleware` already restricts to
    `FRONTEND_HOST`. Tracking every deployment's hostname a second time here
    would add nothing.
    """
    mcp_server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    async with mcp_server.session_manager.run():
        yield
