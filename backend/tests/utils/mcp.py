"""
The MCP test helper (spec #252, #325): performs the protocol handshake over
HTTP against `/mcp`, through the app's test client, with a bot user's token
in the `Authorization` header exactly as a real agent sends it — never the
MCP library's own in-process client, because the token is half of what every
test here is about.

A test reads as one call:

```python
whoami = call_tool(client, bot_headers(client, owner), "whoami")
```

`/mcp` runs stateless (`app.mcp.gateway.run`, #325): the server never mints a
session id, so there is no session id for this helper to carry either.
`start_session` still performs `initialize` then `notifications/initialized`
— the handshake a real client still sends — but only to get a tool call past
those two messages; nothing here remembers a session id, because there is
none to remember. `rpc` still takes an optional `session_id` for a test about
the handshake itself: one that wants to send a bogus `Mcp-Session-Id` and
confirm the server answers anyway (#325's whole point).
"""

import json
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi.testclient import TestClient
from mcp.types import LATEST_PROTOCOL_VERSION

from app.mcp import MCP_PATH
from tests.utils.accounts import READ_ONLY, create_bot_user, token_headers

# Every MCP request here, success or refusal, is a plain JSON body: the app
# mounts the server with `json_response=True` (`app.mcp.run`), so there is no
# SSE stream for a test to read.
_RPC_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def bot_headers(
    client: TestClient,
    owner: dict[str, str],
    *,
    project_ids: list[str] | None = None,
    permissions: dict[str, bool] | None = None,
    name: str = "Agent",
) -> dict[str, str]:
    """
    A new bot user's token, as the headers an MCP request sends it in — the
    one call every MCP test needs to get connected, built on the account
    builder's own `create_bot_user`/`token_headers` rather than a second copy
    of them.
    """
    bot = create_bot_user(
        client,
        owner,
        project_ids=project_ids or [],
        permissions=permissions or READ_ONLY,
        name=name,
    )
    return token_headers(client, owner, bot["id"])


def rpc(
    client: TestClient,
    headers: dict[str, str],
    body: dict[str, Any],
    *,
    session_id: str | None = None,
) -> httpx.Response:
    """
    One JSON-RPC message to `/mcp`, with `headers`' bearer token and,
    when `session_id` is given, an `Mcp-Session-Id` header alongside it — the
    server mints none of its own to carry (#325), so this is only ever a test
    sending one on purpose, to confirm it changes nothing. The low-level seam
    everything else here is built from — a test about a raw protocol message
    reaches for this.
    """
    request_headers = {**_RPC_HEADERS, **headers}
    if session_id is not None:
        request_headers["Mcp-Session-Id"] = session_id
    return client.post(MCP_PATH, json=body, headers=request_headers)


def open_session(client: TestClient, headers: dict[str, str]) -> httpx.Response:
    """
    Send `initialize` and return the raw response, unexamined — for a test
    about the handshake itself (a human session, an unknown or revoked
    token) rather than about a tool, where there is no session yet to call
    one over.
    """
    return rpc(
        client,
        headers,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "taskly-tests", "version": "0.0.0"},
            },
        },
    )


@dataclass(frozen=True)
class McpSession:
    """The headers (bearer token included) that opened a handshake — there is no session id to go with them (#325)."""

    headers: dict[str, str]


def start_session(client: TestClient, headers: dict[str, str]) -> McpSession:
    """
    The full handshake — `initialize`, then the `notifications/initialized`
    the protocol requires before anything else — asserting success at each
    step, so a test that only wants a tool's result never has to. Neither
    message carries a session id: the server mints none (#325).
    """
    initialize = open_session(client, headers)
    assert initialize.status_code == 200, initialize.text

    initialized = rpc(
        client,
        headers,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert initialized.status_code == 202, initialized.text
    return McpSession(headers=headers)


class ToolError(Exception):
    """
    What `call_tool` raises when the tool itself reports a refusal
    (`isError: true`). `message` (also `str(error)`) is the one sentence the
    tool returned — the text a refusal's own description promises (spec
    #247's "a refusal to tell me what to do next").
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def call_tool(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    session: McpSession | None = None,
) -> Any:
    """
    Call tool `name` with `arguments`, over a fresh handshake unless `session`
    is given, and return its result — decoded from JSON, since every tool
    here returns a JSON-serialisable value rather than free text.

    Raises `ToolError` if the tool reported a refusal; an `AssertionError`
    if the HTTP call or the JSON-RPC envelope itself failed, which a
    well-behaved tool call never should.
    """
    opened = session or start_session(client, headers)
    response = rpc(
        client,
        opened.headers,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body.get("error")
    result = body["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        raise ToolError(text)
    return json.loads(text)


def list_tools(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    """The tools the server advertises, name, description and annotations included."""
    session = start_session(client, headers)
    response = rpc(
        client,
        session.headers,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    )
    assert response.status_code == 200, response.text
    tools: list[dict[str, Any]] = response.json()["result"]["tools"]
    return tools
