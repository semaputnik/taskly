"""
`create_task` (spec #247, #255): file a task, a subtask, or a recurring one,
driven over the protocol with a bot user's token, the same way an agent
would.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    READ_ONLY,
    archive_project,
    create_bot_user,
    create_project,
    create_task_record,
    create_user_headers,
    inbox_project_id,
    my_id,
)
from tests.utils.mcp import ToolError, bot_headers, call_tool, list_tools

API = settings.API_V1_STR
TODAY = date.today().isoformat()

# `create_task` writes, so every test needs the one permission that lets a
# bot user do it at all, alongside whatever scope the test is about.
CREATE_ONLY = {"create_tasks": True}


def test_tools_list_advertises_create_task_not_read_only(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    create_task = next(t for t in tools if t["name"] == "create_task")
    assert create_task["description"]
    annotations = create_task.get("annotations") or {}
    assert not annotations.get("readOnlyHint")


def test_creates_a_task_with_every_field_in_one_call(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {
            "title": "Ship it",
            "description": "The whole thing",
            "project": "Work",
            "status": "todo",
            "priority": "P2",
            "due_date": "today",
            "tags": ["release"],
            "assignee": "self",
        },
    )

    assert result["id"]
    assert result["title"] == "Ship it"
    assert result["description"] == "The whole thing"
    assert result["project_id"] == project_id
    assert result["status"] == "todo"
    assert result["priority"] == "P2"
    assert result["due_date"] == TODAY
    assert result["tags"] == ["release"]
    assert result["assignee_bot_user"]["name"] == "Agent"


# --- Project: by name, by id, the Inbox default, ambiguity -------------------


def test_project_is_accepted_by_name_case_insensitively(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client, headers, "create_task", {"title": "T", "project": "work"}
    )
    assert result["project_id"] == project_id


def test_ambiguous_project_name_is_refused_with_matching_ids(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    first = create_project(client, owner, "Dup")
    second = create_project(client, owner, "Dup")
    headers = bot_headers(
        client, owner, project_ids=[first, second], permissions=CREATE_ONLY
    )

    try:
        call_tool(client, headers, "create_task", {"title": "T", "project": "Dup"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "ambiguous_project_name" in exc.message
        assert first in exc.message
        assert second in exc.message


def test_a_task_without_a_project_lands_in_the_inbox_when_in_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    inbox = inbox_project_id(client, owner)
    other = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[inbox, other], permissions=CREATE_ONLY
    )

    result = call_tool(client, headers, "create_task", {"title": "Unsorted"})
    assert result["project_id"] == inbox


def test_a_task_without_a_project_is_refused_when_the_inbox_is_out_of_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    other = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[other], permissions=CREATE_ONLY)

    try:
        call_tool(client, headers, "create_task", {"title": "Unsorted"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message


# --- Subtasks: inheriting and refusing a project of their own ----------------


def test_a_subtask_follows_its_parents_project(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    root = create_task_record(client, owner, "Root", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {"title": "Sub", "parent_task_id": root["id"]},
    )
    assert result["project_id"] == project_id
    assert result["parent_id"] == root["id"]


def test_a_subtask_naming_its_own_project_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    root = create_task_record(client, owner, "Root", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {
                "title": "Sub",
                "parent_task_id": root["id"],
                "project": "Work",
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "invalid_argument" in exc.message
        assert "parent" in exc.message


# --- Status -------------------------------------------------------------------


def test_status_defaults_to_backlog(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client, headers, "create_task", {"title": "T", "project": project_id}
    )
    assert result["status"] == "backlog"


def test_a_named_status_is_honored(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {"title": "T", "project": project_id, "status": "waiting"},
    )
    assert result["status"] == "waiting"


# --- Recurrence -----------------------------------------------------------


def test_a_recurring_task_is_created_with_its_frequency(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {
            "title": "Water the plants",
            "project": project_id,
            "due_date": "today",
            "recurrence": {"frequency": "every_n_days", "interval_days": 3},
        },
    )
    assert result["recurrence"] == {
        "frequency": "every_n_days",
        "interval_days": 3,
    }


def test_a_recurring_task_without_a_due_date_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {
                "title": "T",
                "project": project_id,
                "recurrence": {"frequency": "weekly"},
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "A recurring task needs a due date" in exc.message


def test_a_recurring_subtask_is_refused(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {
                "title": "Sub",
                "parent_task_id": root["id"],
                "due_date": "today",
                "recurrence": {"frequency": "daily"},
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "Only a task at the top of its tree can recur" in exc.message


def test_a_recurring_task_created_done_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {
                "title": "T",
                "project": project_id,
                "due_date": "today",
                "status": "done",
                "recurrence": {"frequency": "daily"},
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "Only an open task can recur" in exc.message


# --- Assignee -------------------------------------------------------------


def test_assignee_self_names_the_connecting_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=CREATE_ONLY,
        name="Agent",
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {"title": "T", "project": project_id, "assignee": "self"},
    )
    assert result["assignee_bot_user"]["name"] == "Agent"


def test_assignee_owner_names_the_human_owner(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    owner_id = my_id(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {"title": "T", "project": project_id, "assignee": "owner"},
    )
    assert result["assignee_id"] == owner_id
    assert result["assignee_bot_user"] is None


def test_assignee_by_another_bot_users_id(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    target = create_bot_user(
        client,
        owner,
        project_ids=[],
        permissions=READ_ONLY,
        name="Triage bot",
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {"title": "T", "project": project_id, "assignee": target["id"]},
    )
    assert result["assignee_bot_user"]["name"] == "Triage bot"


def test_assignee_outside_the_owners_bots_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    other_owner = create_user_headers(client, db)
    stranger = create_bot_user(
        client, other_owner, project_ids=[], permissions=READ_ONLY
    )
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {"title": "T", "project": project_id, "assignee": stranger["id"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "only be assigned to you or to one of your bot users" in exc.message


def test_an_invalid_assignee_string_is_refused(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {"title": "T", "project": project_id, "assignee": "whoever"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "invalid_argument" in exc.message


def test_a_deleted_bot_user_takes_no_new_task(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    target = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY, name="Retired"
    )
    r = client.delete(f"{API}/bot-users/{target['id']}", headers=owner)
    assert r.status_code == 200, r.text
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {"title": "T", "project": project_id, "assignee": target["id"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "is deleted and takes no new tasks" in exc.message


# --- Tags -------------------------------------------------------------------


def test_tags_are_applied_by_name(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={**CREATE_ONLY, "create_tags": True},
    )

    result = call_tool(
        client,
        headers,
        "create_task",
        {"title": "T", "project": project_id, "tags": ["urgent", "ci"]},
    )
    assert sorted(result["tags"]) == ["ci", "urgent"]


def test_a_new_tag_name_needs_the_grant_and_names_the_new_ones(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {
                "title": "T",
                "project": project_id,
                "tags": ["urgent", "brand-new"],
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        # Only the name that was new, never the one already a tag.
        assert "brand-new" in exc.message
        assert "urgent" not in exc.message


# --- Reporter ---------------------------------------------------------------


def test_the_reporter_is_always_the_bot_user(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=CREATE_ONLY,
        name="Filing bot",
    )

    task = call_tool(
        client, headers, "create_task", {"title": "T", "project": project_id}
    )

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    [entry] = [e for e in entries if e["entity_id"] == task["id"]]
    assert entry["actor_bot_user_name"] == "Filing bot"
    assert entry["actor_id"] is None


# --- Refusals: permission, scope, archive ------------------------------------


def test_without_create_tasks_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id], permissions={})

    try:
        call_tool(client, headers, "create_task", {"title": "T", "project": project_id})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "permission_not_granted" in exc.message
        assert "create tasks" in exc.message


def test_a_project_outside_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, "In scope")
    outside = create_project(client, owner, "Outside")
    headers = bot_headers(
        client, owner, project_ids=[in_scope], permissions=CREATE_ONLY
    )

    try:
        call_tool(client, headers, "create_task", {"title": "T", "project": outside})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "outside_scope" in exc.message
        assert "Outside" in exc.message


def test_the_archive_refuses_creation(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    try:
        call_tool(client, headers, "create_task", {"title": "T", "project": project_id})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "project_archived" in exc.message


# --- Argument limits, declared in the schema ---------------------------------


def test_an_overlong_title_is_refused_by_its_schema(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {"title": "x" * 256, "project": project_id},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "255" in exc.message


def test_an_overlong_description_is_refused_by_its_schema(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    try:
        call_tool(
            client,
            headers,
            "create_task",
            {
                "title": "T",
                "project": project_id,
                "description": "x" * 2001,
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert "2000" in exc.message
