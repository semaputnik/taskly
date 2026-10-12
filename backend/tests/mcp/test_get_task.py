"""
`get_task` (spec #247, #254): one task read whole, its subtasks, comments and
attachment names included only when asked for.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    archive_project,
    create_bot_user,
    create_project,
    create_task_record,
    create_user_headers,
    my_id,
    token_headers,
)
from tests.utils.mcp import ToolError, bot_headers, call_tool, list_tools

API = settings.API_V1_STR
TOMORROW = date.today().isoformat()


def _add_comment(client: TestClient, headers: dict[str, str], task_id: str, body: str):
    r = client.post(
        f"{API}/tasks/{task_id}/comments/", headers=headers, json={"body": body}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _upload(
    client: TestClient,
    headers: dict[str, str],
    task_id: str,
    filename: str = "notes.txt",
    content: bytes = b"hello world",
):
    r = client.post(
        f"{API}/tasks/{task_id}/attachments/",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_tools_list_advertises_get_task_read_only(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    get_task = next(t for t in tools if t["name"] == "get_task")
    assert get_task["description"]
    assert get_task["annotations"]["readOnlyHint"] is True


def test_get_task_answers_the_full_record(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    task = create_task_record(
        client,
        owner,
        "Ship it",
        project_id=project_id,
        description="The whole thing",
        priority="P2",
        due_date=TOMORROW,
        tags=["ci"],
    )
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(client, headers, "get_task", {"task_id": task["id"]})

    assert result["id"] == task["id"]
    assert result["title"] == "Ship it"
    assert result["description"] == "The whole thing"
    assert result["status"] == "backlog"
    assert result["priority"] == "P2"
    assert result["due_date"] == TOMORROW
    assert result["project_id"] == project_id
    assert result["tags"] == ["ci"]
    assert result["created_at"] is not None
    assert result["subtask_count"] == 0
    assert "subtasks" not in result
    assert "comments" not in result
    assert "attachments" not in result


def test_get_task_accepts_the_short_id_prefix(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "Root", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])

    short_id = task["id"].replace("-", "")[:8]
    result = call_tool(client, headers, "get_task", {"task_id": short_id})
    assert result["id"] == task["id"]


def test_a_subtask_reports_its_root_tasks_project(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    root = create_task_record(client, owner, "Root", project_id=project_id)
    sub = create_task_record(client, owner, "Sub", parent_id=root["id"])
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(client, headers, "get_task", {"task_id": sub["id"]})
    assert result["project_id"] == project_id


def test_a_bot_users_handover_to_review_is_reported(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    task = create_task_record(client, owner, "Handed over", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    owner_id = my_id(client, owner)

    r = client.patch(
        f"{API}/tasks/{task['id']}",
        headers=headers,
        json={"status": "review", "assignee_id": owner_id},
    )
    assert r.status_code == 200, r.text

    result = call_tool(client, headers, "get_task", {"task_id": task["id"]})
    assert result["handover"] is not None
    assert result["handover"]["bot_user"]["name"] == "Agent"


# include_subtasks


def test_include_subtasks_lists_direct_subtasks_as_compact_lines(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    root = create_task_record(client, owner, "Root", project_id=project_id)
    create_task_record(client, owner, "Sub one", parent_id=root["id"])
    sub_two = create_task_record(client, owner, "Sub two", parent_id=root["id"])
    r = client.patch(
        f"{API}/tasks/{sub_two['id']}", headers=owner, json={"status": "done"}
    )
    assert r.status_code == 200, r.text
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(
        client, headers, "get_task", {"task_id": root["id"], "include_subtasks": True}
    )
    subtasks = {row["title"]: row for row in result["subtasks"]}
    assert set(subtasks) == {"Sub one", "Sub two"}
    assert subtasks["Sub one"]["status"] == "backlog"
    assert subtasks["Sub two"]["status"] == "done"
    # A subtask reports the root's project, like everywhere else (FR-02.4).
    assert subtasks["Sub one"]["project"] == "Work"


def test_without_include_subtasks_no_subtasks_key_is_present(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    create_task_record(client, owner, "Sub", parent_id=root["id"])
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(client, headers, "get_task", {"task_id": root["id"]})
    assert "subtasks" not in result


# include_comments


def test_include_comments_lists_authors_and_moments(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    task = create_task_record(client, owner, "Task", project_id=project_id)
    _add_comment(client, owner, task["id"], "From the owner")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS, name="Agent"
    )
    _add_comment(client, headers, task["id"], "From the bot")

    result = call_tool(
        client, headers, "get_task", {"task_id": task["id"], "include_comments": True}
    )
    comments = result["comments"]
    assert [c["body"] for c in comments] == ["From the owner", "From the bot"]
    assert comments[0]["author"] == "owner"
    assert comments[1]["author"] == "Agent"
    assert comments[0]["created_at"] is not None


# include_attachments


def test_include_attachments_lists_names_and_sizes_never_bytes(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "Task", project_id=project_id)
    _upload(client, owner, task["id"], filename="notes.txt", content=b"hello world")
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(
        client,
        headers,
        "get_task",
        {"task_id": task["id"], "include_attachments": True},
    )
    [attachment] = result["attachments"]
    assert attachment == {"filename": "notes.txt", "size": len(b"hello world")}


# Refusals: permission, scope, and the archive


def test_without_read_tasks_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "Task", project_id=project_id)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions={}, name="No read"
    )
    headers = token_headers(client, owner, bot["id"])

    try:
        call_tool(client, headers, "get_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "read tasks" in exc.message


def test_a_task_outside_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, name="In scope")
    outside = create_project(client, owner, name="Outside")
    task = create_task_record(client, owner, "Task", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[in_scope])

    try:
        call_tool(client, headers, "get_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


def test_a_task_in_the_archive_is_refused(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Shelved")
    task = create_task_record(client, owner, "Task", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])

    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    try:
        call_tool(client, headers, "get_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "project_archived" in exc.message


def test_a_task_not_there_at_all_is_refused(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])

    try:
        call_tool(
            client,
            headers,
            "get_task",
            {"task_id": "00000000-0000-0000-0000-000000000000"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "not_found" in exc.message
