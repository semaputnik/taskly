"""
`complete_task` (spec #247, #257): close a task, answer for its subtasks,
meet the next occurrence — driven over the protocol with a bot user's token,
the same way an agent would.
"""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    archive_project,
    create_project,
    create_recurring_task,
    create_task_record,
    create_user_headers,
)
from tests.utils.mcp import ToolError, bot_headers, call_tool, list_tools

API = settings.API_V1_STR

# `complete_task` writes, so every test needs the one permission that lets a
# bot user close a task at all, alongside whatever scope the test is about.
COMPLETE_ONLY = {"update_tasks": True}


def _get(client: TestClient, headers: dict[str, str], task_id: str) -> dict[str, Any]:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _comments(client: TestClient, headers: dict[str, str], task_id: str) -> list[Any]:
    r = client.get(f"{API}/tasks/{task_id}/comments/", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_tools_list_advertises_complete_task_as_consequential(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    complete_task = next(t for t in tools if t["name"] == "complete_task")
    assert complete_task["description"]
    annotations = complete_task.get("annotations") or {}
    assert annotations.get("destructiveHint")
    assert not annotations.get("readOnlyHint")


# --- No subtasks: the id is enough -------------------------------------------


def test_closing_a_task_with_no_open_subtasks_needs_only_its_id(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "Ship it", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    result = call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    assert result["status"] == "done"
    assert result["title"] == "Ship it"
    assert "already_done" not in result
    assert "next_occurrence" not in result


def test_a_short_id_prefix_resolves(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    result = call_tool(
        client, headers, "complete_task", {"task_id": task["id"][:8]}
    )
    assert result["id"] == task["id"]
    assert result["status"] == "done"


# --- Open subtasks: the directive required, the refusal names them ----------


def test_closing_a_parent_with_open_subtasks_is_refused_naming_them(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    try:
        call_tool(client, headers, "complete_task", {"task_id": root["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "task_has_uncompleted_subtasks" in exc.message
        assert "Child" in exc.message
        assert child["id"][:8] in exc.message
        assert "complete" in exc.message
        assert "leave_uncompleted" in exc.message
    assert _get(client, owner, root["id"])["status"] == "backlog"


def test_answering_complete_closes_the_subtasks_too(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "complete_task",
        {"task_id": root["id"], "subtasks": "complete"},
    )

    assert result["status"] == "done"
    assert _get(client, owner, child["id"])["status"] == "done"


def test_answering_leave_uncompleted_leaves_them_as_they_were(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(
        client, owner, "Child", parent_id=root["id"], status="waiting"
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "complete_task",
        {"task_id": root["id"], "subtasks": "leave_uncompleted"},
    )

    assert result["status"] == "done"
    assert _get(client, owner, child["id"])["status"] == "waiting"


# --- Already done: a no-op, said plainly -------------------------------------


def test_closing_an_already_done_task_changes_nothing_and_says_so(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )
    call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    result = call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    assert result["status"] == "done"
    assert result["already_done"] is True
    assert "next_occurrence" not in result


def test_the_subtasks_answer_is_refused_on_a_call_that_closes_nothing(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )
    call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    try:
        call_tool(
            client,
            headers,
            "complete_task",
            {"task_id": task["id"], "subtasks": "complete"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "invalid_argument" in exc.message
        assert "already done" in exc.message


# --- Recurrence: the next occurrence reported, to the series' own schedule --


def test_closing_a_recurring_occurrence_reports_the_next_ones_id_and_due_date(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    due = date(2026, 3, 2)
    task = create_recurring_task(client, owner, due, project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    result = call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    assert result["status"] == "done"
    next_occurrence = result["next_occurrence"]
    assert next_occurrence["due_date"] == (due + timedelta(days=7)).isoformat()

    successor = _get_by_short_id(client, owner, next_occurrence["id"])
    assert successor["id"] != task["id"]
    assert successor["status"] == "todo"
    assert successor["due_date"] == next_occurrence["due_date"]


def test_the_next_due_date_is_counted_from_the_schedule_not_the_closing_moment(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    due = date.today() - timedelta(days=17)
    task = create_recurring_task(client, owner, due, project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    result = call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    # From the due date, not from today — even though that is still overdue.
    assert result["next_occurrence"]["due_date"] == (due + timedelta(days=7)).isoformat()


def test_closing_an_occurrence_leaves_exactly_one_open_occurrence(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(
        client, owner, date(2026, 3, 2), project_id=project_id, title="Water the plants"
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    call_tool(client, headers, "complete_task", {"task_id": task["id"]})

    r = client.get(f"{API}/tasks/", headers=owner)
    assert r.status_code == 200, r.text
    matching = [t for t in r.json()["data"] if t["title"] == "Water the plants"]
    open_ones = [t for t in matching if t["status"] != "done"]
    assert len(matching) == 2
    assert len(open_ones) == 1


def _get_by_short_id(
    client: TestClient, headers: dict[str, str], short_id: str
) -> dict[str, Any]:
    r = client.get(f"{API}/tasks/", headers=headers)
    assert r.status_code == 200, r.text
    [found] = [t for t in r.json()["data"] if t["id"].replace("-", "").startswith(
        short_id
    )]
    return found


# --- Comment: recorded in the same call, its own grant checked first --------


def test_a_comment_is_recorded_as_the_bot_users_in_the_same_call(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={**COMPLETE_ONLY, "add_comments": True},
        name="Closer bot",
    )

    result = call_tool(
        client,
        headers,
        "complete_task",
        {"task_id": task["id"], "comment": "Shipped and verified."},
    )

    assert result["status"] == "done"
    [recorded] = _comments(client, owner, task["id"])
    assert recorded["body"] == "Shipped and verified."
    assert recorded["author_bot_user"]["name"] == "Closer bot"


def test_a_comment_without_the_grant_is_refused_by_name_before_anything_closes(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "complete_task",
            {"task_id": task["id"], "comment": "Done."},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "add comments" in exc.message

    assert _get(client, owner, task["id"])["status"] == "backlog"
    assert _comments(client, owner, task["id"]) == []


# --- Refusals: permission, scope, archive ------------------------------------


def test_without_update_tasks_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id], permissions={})

    try:
        call_tool(client, headers, "complete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "update tasks" in exc.message


def test_outside_scope_is_refused_by_name(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    inside = create_project(client, owner, "Inside")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[inside], permissions=COMPLETE_ONLY)

    try:
        call_tool(client, headers, "complete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


def test_the_archive_refuses_a_close(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=COMPLETE_ONLY
    )
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    try:
        call_tool(client, headers, "complete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "project_archived" in exc.message
