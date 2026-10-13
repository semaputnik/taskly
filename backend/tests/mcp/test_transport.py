"""
`/mcp`: the transport and its authorisation (spec #252). A bot user's token
identifies the caller through the same path the REST API uses (`app.api.
deps.get_mcp_caller`), a human session is refused for what it is, and a
protocol session is bound to the token that opened it.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.mcp import MCP_PATH
from tests.utils.accounts import (
    READ_ONLY,
    create_bot_user,
    create_project,
    create_user_headers,
    token_headers,
)
from tests.utils.mcp import (
    bot_headers,
    call_tool,
    list_tools,
    open_session,
    rpc,
    start_session,
)

API = settings.API_V1_STR


def test_mcp_is_outside_the_versioned_api_prefix() -> None:
    assert not MCP_PATH.startswith(API)


def test_no_credentials_is_unauthorized(client: TestClient) -> None:
    r = open_session(client, {})
    assert r.status_code == 401


def test_a_human_session_is_refused_for_what_it_is_not_a_permission(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    r = open_session(client, owner)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "bot_only"


def test_a_revoked_expired_or_deleted_bot_users_token_is_the_same_401(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)

    revoked_bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=READ_ONLY, name="Revoked"
    )
    revoked_headers = token_headers(client, owner, revoked_bot["id"])
    r = client.delete(f"{API}/bot-users/{revoked_bot['id']}/token", headers=owner)
    assert r.status_code == 200, r.text

    deleted_bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=READ_ONLY, name="Deleted"
    )
    deleted_headers = token_headers(client, owner, deleted_bot["id"])
    r = client.delete(f"{API}/bot-users/{deleted_bot['id']}", headers=owner)
    assert r.status_code == 200, r.text

    unknown = {"Authorization": "Bearer taskly_bot_" + "x" * 43}

    for headers in (revoked_headers, deleted_headers, unknown):
        r = open_session(client, headers)
        assert r.status_code == 401


def test_tools_list_is_refused_the_same_way_as_initialize(
    client: TestClient, db: Session
) -> None:
    """
    Refusal happens before any MCP message is read, so a bad token never
    gets as far as opening a session to list tools with.
    """
    owner = create_user_headers(client, db)
    r = rpc(client, owner, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "bot_only"


def test_tools_call_is_refused_the_same_way_as_initialize(
    client: TestClient, db: Session
) -> None:
    """The same refusal, for the method a tool call actually uses."""
    owner = create_user_headers(client, db)
    r = rpc(
        client,
        owner,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "whoami", "arguments": {}},
        },
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "bot_only"


def test_a_session_id_presented_with_a_different_token_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    opener = bot_headers(client, owner, project_ids=[project_id], name="Opener")
    other = bot_headers(client, owner, project_ids=[project_id], name="Other")

    session = start_session(client, opener)
    r = rpc(
        client,
        other,
        {"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
        session_id=session.session_id,
    )
    assert r.status_code == 401


def test_the_same_token_may_continue_its_own_session(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)
    session = start_session(client, headers)

    r = rpc(
        client,
        headers,
        {"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
        session_id=session.session_id,
    )
    assert r.status_code == 200, r.text


def test_two_bot_users_with_different_scopes_are_served_through_the_same_endpoint(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    first_project = create_project(client, owner, name="First")
    second_project = create_project(client, owner, name="Second")
    alpha = bot_headers(client, owner, project_ids=[first_project], name="Alpha")
    beta = bot_headers(client, owner, project_ids=[second_project], name="Beta")

    alpha_who = call_tool(client, alpha, "whoami")
    beta_who = call_tool(client, beta, "whoami")

    assert [p["id"] for p in alpha_who["projects"]] == [first_project]
    assert [p["id"] for p in beta_who["projects"]] == [second_project]
    assert alpha_who["actor"]["name"] == "Alpha"
    assert beta_who["actor"]["name"] == "Beta"


# Registration: one `tools/list` call covers every tool's own annotations
# (#302) — each tool used to assert this for itself, over its own protocol
# round trip; the decorator's wiring is the one thing here that can only be
# checked this way, so it is checked once, for all eleven at once, rather
# than eleven times.

_EXPECTED_ANNOTATIONS = {
    "whoami": {"readOnlyHint": True},
    "get_task": {"readOnlyHint": True},
    "search_tasks": {"readOnlyHint": True},
    "search_activity": {"readOnlyHint": True},
    "list_completions": {"readOnlyHint": True},
    "list_tags": {"readOnlyHint": True},
    "create_task": {},
    "comment_task": {},
    "update_task": {"idempotentHint": True},
    "complete_task": {"destructiveHint": True},
    "delete_task": {"destructiveHint": True},
}


def test_tools_advertise_their_annotations(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = {t["name"]: t for t in list_tools(client, headers)}
    assert set(tools) == set(_EXPECTED_ANNOTATIONS)

    for name, expected in _EXPECTED_ANNOTATIONS.items():
        tool = tools[name]
        assert tool["description"], name
        annotations = tool.get("annotations") or {}
        for flag in ("readOnlyHint", "destructiveHint", "idempotentHint"):
            assert bool(annotations.get(flag)) == bool(expected.get(flag)), (
                name,
                flag,
            )


# The refusal envelope: what a tool call that fails actually puts on the
# wire, underneath `tests.utils.mcp.call_tool`'s own `ToolError` (#302) —
# every other refusal test here reaches for a tool body directly and never
# sees this shape at all.


def test_the_refusal_envelope_is_a_code_and_one_sentence_iserror_true(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)
    session = start_session(client, headers)

    response = rpc(
        client,
        session.headers,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_task",
                "arguments": {"task_id": "00000000-0000-0000-0000-000000000000"},
            },
        },
        session_id=session.session_id,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body.get("error")
    result = body["result"]
    assert result["isError"] is True
    [content] = result["content"]
    assert content["type"] == "text"
    # The SDK's own tool runner prefixes every failure, anticipated or not,
    # with "Error executing tool <name>: " (`mcp.server.mcpserver.tools.base.
    # ToolRunner.run`); what a tool itself raises (`app.mcp.conventions.refuse`)
    # is the "<code>: <message>" after that prefix — never a bare status code.
    prefix = "Error executing tool get_task: "
    assert content["text"].startswith(prefix)
    code, _, message = content["text"].removeprefix(prefix).partition(": ")
    assert code == "not_found"
    assert message
