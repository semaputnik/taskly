"""
`comment_task` (spec #247, #258): leave a note on a task, authored by the bot
user, append-only — driven over the protocol with a bot user's token, the
same way an agent would.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    archive_project,
    create_project,
    create_task_record,
    create_user_headers,
)
from tests.utils.mcp import ToolError, bot_headers, call_tool, list_tools

API = settings.API_V1_STR

# `comment_task` writes a comment, so every test needs the one permission
# that lets a bot user do that at all, alongside whatever scope the test is
# about. It is deliberately not `update_tasks` — commenting works without it
# (FR-08.10).
COMMENT_ONLY = {"add_comments": True}


def test_tools_list_advertises_comment_task_as_neither_read_only_nor_destructive(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    comment_task = next(t for t in tools if t["name"] == "comment_task")
    assert comment_task["description"]
    annotations = comment_task.get("annotations") or {}
    assert not annotations.get("readOnlyHint")
    assert not annotations.get("destructiveHint")


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

    result = call_tool(
        client,
        headers,
        "comment_task",
        {"task_id": task["id"], "body": "Looked into this; nothing broke."},
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

    result = call_tool(
        client, headers, "comment_task", {"task_id": task["id"][:8], "body": "Noted."}
    )
    assert result["body"] == "Noted."


# --- A blank comment, and the length the schema declares ---------------------


def test_a_blank_comment_is_refused(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )

    try:
        call_tool(
            client, headers, "comment_task", {"task_id": task["id"], "body": "  "}
        )
        raise AssertionError("expected a refusal")
    except ToolError:
        pass

    r = client.get(f"{API}/tasks/{task['id']}/comments/", headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["data"] == []


def test_an_overlong_comment_is_refused_by_its_schema(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "comment_task",
            {"task_id": task["id"], "body": "x" * 10001},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "10000" in exc.message


# --- Grants: comment works without update_tasks, and is refused by name -----


def test_commenting_needs_no_update_permission(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )

    result = call_tool(
        client, headers, "comment_task", {"task_id": task["id"], "body": "Still fine."}
    )
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

    try:
        call_tool(
            client, headers, "comment_task", {"task_id": task["id"], "body": "No."}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "add comments" in exc.message


# --- Refusals: scope, archive -------------------------------------------------


def test_outside_scope_is_refused_by_name(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    inside = create_project(client, owner, "Inside")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[inside], permissions=COMMENT_ONLY)

    try:
        call_tool(
            client, headers, "comment_task", {"task_id": task["id"], "body": "No."}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


def test_the_archive_refuses_a_comment(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    try:
        call_tool(
            client, headers, "comment_task", {"task_id": task["id"], "body": "No."}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "project_archived" in exc.message
