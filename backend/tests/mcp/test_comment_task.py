"""
`comment_task` (spec #247, #258): leave a note on a task, authored by the bot
user, append-only.

Exercised against `comment_task_body` directly (#302) — see
`test_whoami.py`'s own module docstring for why, and where the protocol
itself is still tested.
"""

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.comment_task import comment_task_body
from tests.utils.accounts import (
    archive_project,
    create_project,
    create_task_record,
    create_user_headers,
)
from tests.utils.mcp import ToolError as ProtocolToolError
from tests.utils.mcp import bot_headers, call_tool
from tests.utils.mcp_body import caller_for

API = settings.API_V1_STR

# `comment_task` writes a comment, so every test needs the one permission
# that lets a bot user do that at all, alongside whatever scope the test is
# about. It is deliberately not `update_tasks` — commenting works without it
# (FR-08.10).
COMMENT_ONLY = {"add_comments": True}


def test_a_comment_is_recorded_as_the_bot_users_and_returned(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=COMMENT_ONLY,
        name="Notetaker",
    )
    caller = caller_for(db, headers)

    result = comment_task_body(
        db, caller, task_id=task["id"], body="Looked into this; nothing broke."
    )

    assert result["body"] == "Looked into this; nothing broke."
    assert result["author_bot_user"]["name"] == "Notetaker"

    r = client.get(f"{API}/tasks/{task['id']}/comments/", headers=owner)
    assert r.status_code == 200, r.text
    [recorded] = r.json()["data"]
    assert recorded["body"] == "Looked into this; nothing broke."
    assert recorded["author_bot_user"]["name"] == "Notetaker"


def test_a_short_id_prefix_resolves(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )
    caller = caller_for(db, headers)

    result = comment_task_body(db, caller, task_id=task["id"][:8], body="Noted.")
    assert result["body"] == "Noted."


# --- A blank comment, and the length the schema declares ---------------------


def test_a_blank_or_overlong_comment_is_refused_by_its_schema(
    client: TestClient, db: Session
) -> None:
    """
    `body` is trimmed and bounded to 1–10,000 characters by `CommentBody`,
    the tool's own argument schema — enforced by the MCP SDK before a call
    ever reaches `comment_task_body`, so this is the one pair of checks here
    that genuinely needs the protocol rather than a direct body call.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )

    try:
        call_tool(client, headers, "comment_task", {"task_id": task["id"], "body": "  "})
        raise AssertionError("expected a refusal")
    except ProtocolToolError:
        pass

    try:
        call_tool(
            client,
            headers,
            "comment_task",
            {"task_id": task["id"], "body": "x" * 10001},
        )
        raise AssertionError("expected a refusal")
    except ProtocolToolError as exc:
        assert "10000" in exc.message

    r = client.get(f"{API}/tasks/{task['id']}/comments/", headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["data"] == []


# --- Grants: comment works without update_tasks, and is refused by name -----


def test_commenting_needs_no_update_permission(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )
    caller = caller_for(db, headers)

    result = comment_task_body(db, caller, task_id=task["id"], body="Still fine.")
    assert result["body"] == "Still fine."


def test_without_add_comments_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={"update_tasks": True},
    )
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        comment_task_body(db, caller, task_id=task["id"], body="No.")
    message = str(exc_info.value)
    assert "permission_not_granted" in message
    assert "add comments" in message


# --- Refusals: scope, archive -------------------------------------------------


def test_outside_scope_is_refused_by_name(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    inside = create_project(client, owner, "Inside")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[inside], permissions=COMMENT_ONLY)
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        comment_task_body(db, caller, task_id=task["id"], body="No.")
    message = str(exc_info.value)
    assert "outside_scope" in message
    assert "Outside" in message


def test_the_archive_refuses_a_comment(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )
    caller = caller_for(db, headers)
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    with pytest.raises(ToolError) as exc_info:
        comment_task_body(db, caller, task_id=task["id"], body="No.")
    assert "project_archived" in str(exc_info.value)
