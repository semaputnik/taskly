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

This module is wiring only: the ASGI boundary, the session-to-token binding,
and `mount`/`run`. The server instance every tool registers on lives in
`app.mcp.server`; the rules a tool's arguments, output and refusals follow
live in `app.mcp.conventions`; the tools themselves live in `app.mcp.tools`,
one module per tool (or per small group), imported by `app.mcp.tools`'s own
`__init__` so each registers itself with `@mcp_server.tool(...)` on import. A
new tool adds a module there and nothing here.
"""

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER
from mcp.server.transport_security import TransportSecuritySettings
from sqlmodel import Session
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

from app.api.deps import get_mcp_caller
from app.core import security
from app.core.db import engine
from app.mcp import tools as _tools  # noqa: F401 — import registers every tool
from app.mcp.conventions import bearer_token
from app.mcp.server import mcp_server

MCP_PATH = "/mcp"


class _BotGateway:
    """
    The ASGI boundary at `/mcp`: resolves every request's bearer token with
    `get_mcp_caller` before any MCP message on it is processed, and binds a
    protocol session to the token that opened it (spec #252).

    Session ids are the SDK's own (`Mcp-Session-Id`): minted on `initialize`,
    carried on every later call. `_session_tokens` remembers, in this
    process's memory, which token's hash opened each one — exactly where the
    SDK keeps the rest of a stateful session's state (`stateless_http` is
    `False`); there is no load balancer sharing sessions across processes to
    worry about here. A session id presented with a different token is
    refused rather than served, so one agent's session cannot be continued
    as another's.
    """

    def __init__(self) -> None:
        # Not a session manager captured once: `run()` below builds a fresh
        # one every time this app's lifespan starts (a FastAPI process
        # restart in production, a new `TestClient(app)` context between
        # test modules here), and `StreamableHTTPSessionManager.run()`
        # refuses to be called twice on the same instance. Reading
        # `mcp_server.session_manager` per request always finds the live one.
        self._session_tokens: dict[str, str] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # A route only ever receives the "http" scope type (routing for
        # "lifespan" and "websocket" happens above it); this app never opens
        # a websocket, and "http" covers the SSE GET stream too, so there is
        # nothing else to branch on here.
        session_manager = mcp_server.session_manager
        headers = Headers(scope=scope)
        try:
            token = bearer_token(headers)
            with Session(engine) as session:
                get_mcp_caller(session, token)
        except HTTPException as exc:
            await _deny(scope, receive, send, exc.status_code, exc.detail)
            return

        token_hash = security.hash_bot_token(token)
        session_id = headers.get(MCP_SESSION_ID_HEADER)
        if session_id is not None:
            opened_with = self._session_tokens.get(session_id)
            if opened_with is not None and opened_with != token_hash:
                await _deny(
                    scope,
                    receive,
                    send,
                    401,
                    {
                        "code": "session_token_mismatch",
                        "message": (
                            "This MCP session was opened with a different "
                            "token. Start a new session with this one."
                        ),
                    },
                )
                return

        async def remember_session(message: Message) -> None:
            if message["type"] == "http.response.start":
                minted = _header_value(message["headers"], MCP_SESSION_ID_HEADER)
                if minted is not None:
                    self._session_tokens.setdefault(minted, token_hash)
                if scope["method"] == "DELETE" and session_id is not None:
                    # The client just terminated this session (or tried to);
                    # either way, nothing will present this id again
                    # legitimately, so forget which token owned it.
                    self._session_tokens.pop(session_id, None)
            await send(message)

        await session_manager.handle_request(scope, receive, remember_session)

    def reset(self) -> None:
        """Forget every session-to-token binding; called as `run()` starts a fresh session manager."""
        self._session_tokens.clear()


_gateway = _BotGateway()


def _header_value(raw_headers: Iterable[tuple[bytes, bytes]], name: str) -> str | None:
    """A header's value from a raw ASGI header list, by name, lower-cased."""
    target = name.encode("latin-1")
    for key, value in raw_headers:
        if key.lower() == target:
            return value.decode("latin-1")
    return None


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
        methods=["GET", "POST", "DELETE"],
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
    gets its own, and `_gateway.reset()` drops every session-to-token
    binding from the one before, which no longer exists to be confused with.

    `MCPServer.streamable_http_app()` is the only way `MCPServer` builds a
    session manager at all; its returned Starlette app is never mounted (see
    `mount`) — only the side effect of its being built is wanted here.

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
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    _gateway.reset()
    async with mcp_server.session_manager.run():
        yield
