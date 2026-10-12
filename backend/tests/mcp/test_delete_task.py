"""
`delete_task` (spec #247, #258): take a task down on purpose, subtree
included — driven over the protocol with a bot user's token, the same way
an agent would.
"""

from typing import Any

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

# `delete_task` writes, so every test needs the one permission that lets a
# bot user delete a task at all, alongside whatever scope the test is about.
DELETE_ONLY = {"delete_tasks": True}


def _get(client: TestClient, headers: dict[str, str], task_id: str) -> Any:
    return client.get(f"{API}/tasks/{task_id}", headers=headers)


def test_tools_list_advertises_delete_task_as_destructive(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    delete_task = next(t for t in tools if t["name"] == "delete_task")
    assert delete_task["description"]
    annotations = delete_task.get("annotations") or {}
    assert annotations.get("destructiveHint")
    assert not annotations.get("readOnlyHint")


# --- No subtasks: the id is enough -------------------------------------------


def test_deleting_a_task_with_no_subtasks_needs_only_its_id(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "Scrap it", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )

    result = call_tool(client, headers, "delete_task", {"task_id": task["id"]})

    assert result["deleted"] is True
    assert result["title"] == "Scrap it"
    assert _get(client, owner, task["id"]).status_code == 404


def test_a_short_id_prefix_resolves(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )

    result = call_tool(client, headers, "delete_task", {"task_id": task["id"][:8]})
    assert result["deleted"] is True
    assert _get(client, owner, task["id"]).status_code == 404


# --- Subtasks: the directive required, the refusal names them --------------


def test_deleting_a_parent_with_subtasks_is_refused_naming_them(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )

    try:
        call_tool(client, headers, "delete_task", {"task_id": root["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "task_has_subtasks" in exc.message
        assert "Child" in exc.message
        assert child["id"][:8] in exc.message
        assert "delete_subtasks" in exc.message

    assert _get(client, owner, root["id"]).status_code == 200
    assert _get(client, owner, child["id"]).status_code == 200


def test_the_refusal_names_a_done_subtask_too(client: TestClient, db: Session) -> None:
    """
    A delete cascades over the whole subtree, done subtasks included, unlike
    closing one, where only the open ones matter — so the refusal here names
    a done subtask too (`crud.subtasks`, not `crud.open_subtasks`).
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    done_child = create_task_record(
        client, owner, "Done child", parent_id=root["id"], status="done"
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )

    try:
        call_tool(client, headers, "delete_task", {"task_id": root["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "Done child" in exc.message
        assert done_child["id"][:8] in exc.message


def test_confirming_delete_subtasks_takes_the_whole_subtree_down(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    grandchild = create_task_record(client, owner, "Grandchild", parent_id=child["id"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "delete_task",
        {"task_id": root["id"], "delete_subtasks": True},
    )

    assert result["deleted"] is True
    assert _get(client, owner, root["id"]).status_code == 404
    assert _get(client, owner, child["id"]).status_code == 404
    assert _get(client, owner, grandchild["id"]).status_code == 404


# --- Refusals: permission, scope, archive ------------------------------------


def test_without_delete_tasks_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id], permissions={})

    try:
        call_tool(client, headers, "delete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "delete tasks" in exc.message

    assert _get(client, owner, task["id"]).status_code == 200


def test_outside_scope_is_refused_by_name(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    inside = create_project(client, owner, "Inside")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[inside], permissions=DELETE_ONLY)

    try:
        call_tool(client, headers, "delete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


def test_the_archive_refuses_a_delete(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    try:
        call_tool(client, headers, "delete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "project_archived" in exc.message

    assert _get(client, owner, task["id"]).status_code == 200
