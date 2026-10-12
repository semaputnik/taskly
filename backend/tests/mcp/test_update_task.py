"""
`update_task` (spec #247, #256): change a task, move it, hand it over —
driven over the protocol with a bot user's token, the same way an agent
would.
"""

from datetime import date

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    READ_ONLY,
    archive_project,
    create_bot_user,
    create_project,
    create_recurring_task,
    create_task_record,
    create_user_headers,
    my_id,
)
from tests.utils.mcp import ToolError, bot_headers, call_tool, list_tools

API = settings.API_V1_STR
TODAY = date.today().isoformat()

# `update_task` writes, so every test needs the one permission that lets a
# bot user do it at all, alongside whatever scope the test is about.
UPDATE_ONLY = {"update_tasks": True}


def _get(client: TestClient, headers: dict[str, str], task_id: str) -> dict:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _patch(
    client: TestClient, headers: dict[str, str], task_id: str, **fields: object
) -> httpx.Response:
    """A plain REST `PATCH`, for fixtures this test's own tool call is not about."""
    return client.patch(f"{API}/tasks/{task_id}", headers=headers, json=fields)


def test_tools_list_advertises_update_task_as_idempotent_not_read_only(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    update_task = next(t for t in tools if t["name"] == "update_task")
    assert update_task["description"]
    annotations = update_task.get("annotations") or {}
    assert annotations.get("idempotentHint")
    assert not annotations.get("readOnlyHint")


# --- Fields: changed together, left alone when omitted ----------------------


def test_updates_several_fields_leaving_the_rest_alone(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    personal = create_project(client, owner, "Personal")
    task = create_task_record(
        client, owner, "Draft", project_id=work, priority="P3", description="Notes"
    )
    headers = bot_headers(
        client, owner, project_ids=[work, personal], permissions=ALL_PERMISSIONS
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {
            "task_id": task["id"],
            "title": "Shipped",
            "project": "Personal",
            "priority": "P1",
            "due_date": "today",
            "status": "todo",
            "tags": ["release"],
        },
    )

    assert result["title"] == "Shipped"
    assert result["project_id"] == personal
    assert result["priority"] == "P1"
    assert result["due_date"] == TODAY
    assert result["status"] == "todo"
    assert result["tags"] == ["release"]
    # Never asked to change: left exactly as it was.
    assert result["description"] == "Notes"


def test_description_can_be_set_on_its_own(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": task["id"], "description": "What it's for"},
    )
    assert result["description"] == "What it's for"
    assert result["title"] == "T"


def test_a_short_id_prefix_resolves(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": task["id"][:8], "title": "Renamed"},
    )
    assert result["id"] == task["id"]
    assert result["title"] == "Renamed"


# --- Tags: replaced wholesale -------------------------------------------------


def test_tags_replace_wholesale(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(
        client, owner, "T", project_id=project_id, tags=["old", "keep"]
    )
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={**UPDATE_ONLY, "create_tags": True},
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": task["id"], "tags": ["new"]},
    )
    assert result["tags"] == ["new"]


def test_sending_an_empty_tags_list_clears_every_tag(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id, tags=["old"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client, headers, "update_task", {"task_id": task["id"], "tags": []}
    )
    assert result["tags"] == []


def test_a_new_tag_name_needs_the_grant_and_names_the_new_ones(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {"task_id": task["id"], "tags": ["urgent", "brand-new"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "brand-new" in exc.message
        assert "urgent" not in exc.message


# --- Clear: the explicit way to empty a field --------------------------------


def test_clear_empties_description_due_date_priority_and_assignee(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    owner_id = my_id(client, owner)
    task = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        description="Notes",
        due_date=TODAY,
        priority="P2",
        assignee_id=owner_id,
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {
            "task_id": task["id"],
            "clear": ["description", "due_date", "priority", "assignee"],
        },
    )
    assert result["description"] is None
    assert result["due_date"] is None
    assert result["priority"] is None
    assert result["assignee_id"] is None


def test_sending_a_value_and_clearing_the_same_field_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {"task_id": task["id"], "priority": "P1", "clear": ["priority"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "invalid_argument" in exc.message
        assert "priority" in exc.message


def test_a_null_argument_is_refused_rather_than_read_as_clear(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {"task_id": task["id"], "due_date": None},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "invalid_argument" in exc.message
        assert "null" in exc.message


# --- Status: open statuses only, subtasks untouched --------------------------


def test_moving_to_done_is_refused_pointing_to_complete_task(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "status": "done"}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "complete_task" in exc.message


def test_moving_between_open_statuses_leaves_subtasks_alone(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    sub = create_task_record(client, owner, "Sub", parent_id=root["id"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": root["id"], "status": "waiting"},
    )
    assert result["status"] == "waiting"
    assert _get(client, owner, sub["id"])["status"] == "backlog"


# --- Recurrence: the due-date scope, reopening the latest occurrence --------


def test_moving_an_open_occurrences_due_date_needs_a_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {"task_id": task["id"], "due_date": "2026-03-04"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "due_date_scope_required" in exc.message


def test_a_due_date_scope_moves_a_recurring_occurrence(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {
            "task_id": task["id"],
            "due_date": "2026-03-04",
            "due_date_scope": "this_occurrence",
        },
    )
    assert result["due_date"] == "2026-03-04"


def test_a_due_date_scope_on_a_task_that_does_not_recur_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(
        client, owner, "T", project_id=project_id, due_date="2026-03-02"
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {
                "task_id": task["id"],
                "due_date": "2026-03-04",
                "due_date_scope": "this_occurrence",
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "invalid_argument" in exc.message
        assert "recurring task that is open" in exc.message


def test_reopening_an_earlier_occurrence_is_refused_naming_the_latest(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    r = _patch(client, owner, task["id"], status="done")
    assert r.status_code == 200, r.text
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "status": "todo"}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "occurrence_superseded" in exc.message
        assert "latest occurrence" in exc.message


# --- Project: moved, a subtask refused, scope both ways ----------------------


def test_a_task_is_moved_to_another_project_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    personal = create_project(client, owner, "Personal")
    task = create_task_record(client, owner, "T", project_id=work)
    headers = bot_headers(
        client, owner, project_ids=[work, personal], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": task["id"], "project": "Personal"},
    )
    assert result["project_id"] == personal


def test_a_subtask_cannot_be_moved_between_projects(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    personal = create_project(client, owner, "Personal")
    root = create_task_record(client, owner, "Root", project_id=work)
    sub = create_task_record(client, owner, "Sub", parent_id=root["id"])
    headers = bot_headers(
        client, owner, project_ids=[work, personal], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {"task_id": sub["id"], "project": "Personal"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "top of the tree" in exc.message


def test_moving_into_a_project_outside_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=work)
    headers = bot_headers(client, owner, project_ids=[work], permissions=UPDATE_ONLY)

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "project": outside}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


def test_a_task_whose_own_project_is_outside_scope_cannot_be_moved_out_of_it(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    outside = create_project(client, owner, "Outside")
    inside = create_project(client, owner, "Inside")
    task = create_task_record(client, owner, "T", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[inside], permissions=UPDATE_ONLY)

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "project": inside}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        # The task's own project (where it already is) is the one checked
        # first (FR-08.8), before the destination is even looked at.
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


# --- Assignee: owner or a bot user, never the reporter -----------------------


def test_assignee_self_names_the_connecting_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=UPDATE_ONLY,
        name="Agent",
    )

    result = call_tool(
        client, headers, "update_task", {"task_id": task["id"], "assignee": "self"}
    )
    assert result["assignee_bot_user"]["name"] == "Agent"


def test_assignee_owner_names_the_human_owner(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    owner_id = my_id(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    result = call_tool(
        client, headers, "update_task", {"task_id": task["id"], "assignee": "owner"}
    )
    assert result["assignee_id"] == owner_id


def test_a_deleted_bot_user_keeps_what_it_has_but_takes_no_new_task(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    retired = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY, name="Retired"
    )
    task = create_task_record(client, owner, "T", project_id=project_id)
    other_task = create_task_record(
        client, owner, "Already on it", project_id=project_id, assignee_id=retired["id"]
    )
    r = client.delete(f"{API}/bot-users/{retired['id']}", headers=owner)
    assert r.status_code == 200, r.text
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "update_task",
            {"task_id": task["id"], "assignee": retired["id"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "is deleted and takes no new tasks" in exc.message

    # Resending it on the task it already holds is not a new assignment.
    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": other_task["id"], "assignee": retired["id"], "title": "Still mine"},
    )
    assert result["title"] == "Still mine"


# --- Reporter: unreachable by any argument -----------------------------------


def test_the_reporter_is_never_changed_by_update_task(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    reporter_id_before = task["reporter_id"]
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=UPDATE_ONLY,
        name="Agent",
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": task["id"], "assignee": "owner", "status": "review"},
    )
    assert result["reporter_id"] == reporter_id_before


# --- Hand-over: review, assigned to the owner, with a comment ---------------


def test_a_hand_over_leaves_the_task_in_review_on_the_owner_and_shows_it(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    owner_id = my_id(client, owner)
    task = create_task_record(
        client, owner, "T", project_id=project_id, status="in_progress"
    )
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={**UPDATE_ONLY, "add_comments": True},
        name="Agent",
    )

    result = call_tool(
        client,
        headers,
        "update_task",
        {"task_id": task["id"], "status": "review", "assignee": "owner"},
    )
    assert result["status"] == "review"
    assert result["assignee_id"] == owner_id
    assert result["handover"]["bot_user"]["name"] == "Agent"

    c = client.post(
        f"{API}/tasks/{task['id']}/comments/",
        headers=headers,
        json={"body": "Done: shipped the thing."},
    )
    assert c.status_code == 200, c.text


def test_entering_review_alone_does_not_move_the_task_onto_the_owner(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    target = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY, name="Doer bot"
    )
    task = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="in_progress",
        assignee_id=target["id"],
    )
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=UPDATE_ONLY,
        name="Reviewer bot",
    )

    result = call_tool(
        client, headers, "update_task", {"task_id": task["id"], "status": "review"}
    )
    assert result["status"] == "review"
    assert result["assignee_bot_user"]["id"] == target["id"]


# --- Refusals: permission, scope, archive ------------------------------------


def test_without_update_tasks_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id], permissions={})

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "title": "New"}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "update tasks" in exc.message


def test_the_archive_refuses_an_update(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "title": "New"}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "project_archived" in exc.message
