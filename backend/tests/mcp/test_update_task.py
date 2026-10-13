"""
`update_task` (spec #247, #256): change a task, move it, hand it over.

Exercised against `update_task_body` directly (#302) — see
`test_whoami.py`'s own module docstring for why, and where the protocol
itself is still tested. `test_a_null_argument_is_refused_rather_than_read_as_clear`
is the exception: it is `app.mcp.server._RefuseNullArguments`, a `tools/call`
interceptor that inspects the raw JSON arguments before the SDK ever binds
them to `update_task`'s own parameters, so it genuinely needs the protocol.
"""

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.update_task import update_task_body
from app.models import DueDateScope, TaskPriority, TaskStatus
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
from tests.utils.mcp import ToolError as ProtocolToolError
from tests.utils.mcp import bot_headers, call_tool
from tests.utils.mcp_body import caller_for

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
    caller = caller_for(db, headers)

    result = update_task_body(
        db,
        caller,
        task_id=task["id"],
        title="Shipped",
        project="Personal",
        priority=TaskPriority.P1,
        due_date="today",
        status=TaskStatus.TODO,
        tags=["release"],
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
    caller = caller_for(db, headers)

    result = update_task_body(
        db, caller, task_id=task["id"], description="What it's for"
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
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"][:8], title="Renamed")
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
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"], tags=["new"])
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
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"], tags=[])
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(
            db, caller, task_id=task["id"], tags=["urgent", "brand-new"]
        )
    message = str(exc_info.value)
    assert "permission_not_granted" in message
    assert "brand-new" in message
    assert "urgent" not in message


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
    caller = caller_for(db, headers)

    result = update_task_body(
        db,
        caller,
        task_id=task["id"],
        clear=["description", "due_date", "priority", "assignee"],
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(
            db, caller, task_id=task["id"], priority=TaskPriority.P1, clear=["priority"]
        )
    message = str(exc_info.value)
    assert "invalid_argument" in message
    assert "priority" in message


def test_a_null_argument_is_refused_rather_than_read_as_clear(
    client: TestClient, db: Session
) -> None:
    """
    `app.mcp.server._RefuseNullArguments` inspects the raw JSON arguments of
    a `tools/call`, before the SDK binds anything to `update_task`'s own
    parameters — the one check here that genuinely needs the protocol.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    try:
        call_tool(
            client, headers, "update_task", {"task_id": task["id"], "due_date": None}
        )
        raise AssertionError("expected a refusal")
    except ProtocolToolError as exc:
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], status=TaskStatus.DONE)
    assert "complete_task" in str(exc_info.value)


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
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=root["id"], status=TaskStatus.WAITING)
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], due_date="2026-03-04")
    assert "due_date_scope_required" in str(exc_info.value)


def test_a_due_date_scope_moves_a_recurring_occurrence(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )
    caller = caller_for(db, headers)

    result = update_task_body(
        db,
        caller,
        task_id=task["id"],
        due_date="2026-03-04",
        due_date_scope=DueDateScope.THIS_OCCURRENCE,
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(
            db,
            caller,
            task_id=task["id"],
            due_date="2026-03-04",
            due_date_scope=DueDateScope.THIS_OCCURRENCE,
        )
    message = str(exc_info.value)
    assert "invalid_argument" in message
    assert "recurring task that is open" in message


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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], status=TaskStatus.TODO)
    message = str(exc_info.value)
    assert "occurrence_superseded" in message
    assert "latest occurrence" in message


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
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"], project="Personal")
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=sub["id"], project="Personal")
    assert "top of the tree" in str(exc_info.value)


def test_moving_into_a_project_outside_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=work)
    headers = bot_headers(client, owner, project_ids=[work], permissions=UPDATE_ONLY)
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], project=outside)
    message = str(exc_info.value)
    assert "outside_scope" in message
    assert "Outside" in message


def test_a_task_whose_own_project_is_outside_scope_cannot_be_moved_out_of_it(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    outside = create_project(client, owner, "Outside")
    inside = create_project(client, owner, "Inside")
    task = create_task_record(client, owner, "T", project_id=outside)
    headers = bot_headers(client, owner, project_ids=[inside], permissions=UPDATE_ONLY)
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], project=inside)
    message = str(exc_info.value)
    # The task's own project (where it already is) is the one checked first
    # (FR-08.8), before the destination is even looked at.
    assert "outside_scope" in message
    assert "Outside" in message


# --- Assignee: owner or a bot user, never the reporter -----------------------


def test_assignee_self_names_the_connecting_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY, name="Agent"
    )
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"], assignee="self")
    assert result["assignee_bot_user"]["name"] == "Agent"


def test_assignee_owner_names_the_human_owner(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    owner_id = my_id(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"], assignee="owner")
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], assignee=retired["id"])
    assert "is deleted and takes no new tasks" in str(exc_info.value)

    # Resending it on the task it already holds is not a new assignment.
    result = update_task_body(
        db, caller, task_id=other_task["id"], assignee=retired["id"], title="Still mine"
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
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY, name="Agent"
    )
    caller = caller_for(db, headers)

    result = update_task_body(
        db, caller, task_id=task["id"], assignee="owner", status=TaskStatus.REVIEW
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
    caller = caller_for(db, headers)

    result = update_task_body(
        db, caller, task_id=task["id"], status=TaskStatus.REVIEW, assignee="owner"
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
    caller = caller_for(db, headers)

    result = update_task_body(db, caller, task_id=task["id"], status=TaskStatus.REVIEW)
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
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], title="New")
    message = str(exc_info.value)
    assert "permission_not_granted" in message
    assert "update tasks" in message


def test_the_archive_refuses_an_update(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )
    caller = caller_for(db, headers)
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    with pytest.raises(ToolError) as exc_info:
        update_task_body(db, caller, task_id=task["id"], title="New")
    assert "project_archived" in str(exc_info.value)
