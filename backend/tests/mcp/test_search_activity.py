"""
`search_activity` (spec #247, #248, #259): the activity log itself, narrowed
the way `GET /activity-log/` already narrows it, read over MCP as compact
lines. The visibility rules themselves — the scope, the archive, the
all-or-nothing batch rule, the tag exemption, `restorable` and the deletion
id withheld from a bot — are #251's and tested there
(`tests/api/routes/test_activity_for_bots.py`); these tests are about this
tool's own mapping onto that route and its own rendering of a line, built
over a history made through the API the way #248's own testing decision
asks for.

Exercised against `search_activity_body` directly (#302) — see
`test_whoami.py`'s own module docstring for why, and where the protocol
itself is still tested.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.search_activity import search_activity_body
from app.models import ActivityKind, ActivityOrder
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_task_record,
    create_user_headers,
    delete_task,
    token_headers,
)
from tests.utils.mcp import bot_headers
from tests.utils.mcp_body import caller_for

API = settings.API_V1_STR
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)

Headers = dict[str, str]


def _whats(result: dict[str, Any]) -> list[str]:
    entries = result["entries"]
    assert isinstance(entries, list)
    return [entry["what"] for entry in entries]


def _titles(result: dict[str, Any]) -> list[str | None]:
    entries = result["entries"]
    return [entry["subject"].get("title") for entry in entries]


def _task_titles(result: dict[str, Any]) -> list[str | None]:
    """
    Like `_titles`, but only the entries about a task — every fixture here
    also creates the project itself, whose own `project_created` entry
    would otherwise show up as a `None` title under a filter (`kind`,
    `actor`) wide enough to catch it too.
    """
    return [
        entry["subject"].get("title")
        for entry in result["entries"]
        if entry["subject"].get("type") == "task"
    ]


# The grant itself


def test_without_the_grant_is_refused_by_name(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={**ALL_PERMISSIONS, "read_activity": False},
    )
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_activity_body(db, caller)
    message = str(exc_info.value)
    assert "permission_not_granted" in message
    assert "activity log" in message


# Compact lines: the moment, the actor, what happened, the subject


def test_compact_row_shape_for_a_created_task(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Write the report", project_id=project_id)

    result = search_activity_body(
        db, caller, kind=ActivityKind.CREATED, task_id=task["id"]
    )
    [row] = result["entries"]
    assert set(row) == {"at", "actor", "what", "subject"}
    assert row["actor"] == "owner"
    assert row["what"] == "Created in Work"
    assert row["subject"] == {
        "type": "task",
        "id": task["id"].replace("-", "")[:8],
        "title": "Write the report",
    }
    # Nothing a bot user cannot act on leaks through.
    assert "restorable" not in row
    assert "deletion_id" not in row


def test_total_is_reported_and_truncation_names_a_filter_to_narrow_with(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    for i in range(3):
        create_task_record(client, owner, f"Task {i}", project_id=project_id)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)

    result = search_activity_body(db, caller, limit=2)
    assert result["count"] >= 3
    assert len(result["entries"]) == 2
    assert result["truncated"] is True
    assert result["narrow_with"] == "kind"


# kind: non-overlapping groups


def test_kind_completed_and_changed_do_not_overlap(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    completed = create_task_record(client, owner, "Finish me", project_id=project_id)
    changed = create_task_record(
        client, owner, "Reprioritise me", project_id=project_id
    )
    r = client.patch(
        f"{API}/tasks/{completed['id']}", headers=owner, json={"status": "done"}
    )
    assert r.status_code == 200, r.text
    r = client.patch(
        f"{API}/tasks/{changed['id']}", headers=owner, json={"priority": "P1"}
    )
    assert r.status_code == 200, r.text

    done = search_activity_body(db, caller, kind=ActivityKind.COMPLETED)
    assert _titles(done) == ["Finish me"]
    assert _whats(done) == ["Completed"]

    moved = search_activity_body(db, caller, kind=ActivityKind.CHANGED)
    assert "Finish me" not in _titles(moved)
    assert "Reprioritise me" in _titles(moved)


def test_a_batch_completion_is_counted_as_completed_not_changed(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    first = create_task_record(client, owner, "First", project_id=project_id)
    second = create_task_record(client, owner, "Second", project_id=project_id)
    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": [first["id"], second["id"]], "status": "done"},
    )
    assert r.status_code == 200, r.text

    done = search_activity_body(db, caller, kind=ActivityKind.COMPLETED)
    [row] = done["entries"]
    assert row["what"] == "Changed 2 tasks: completed"
    assert row["subject"]["type"] == "tasks"
    assert row["subject"]["count"] == 2
    assert sorted(row["subject"]["ids"]) == sorted(
        task_id.replace("-", "")[:8] for task_id in (first["id"], second["id"])
    )

    assert search_activity_body(db, caller, kind=ActivityKind.CHANGED)["entries"] == []


# task_id: a task's own history, its comments, and the batches that touched it


def test_task_id_narrows_to_its_own_history_including_comments_and_batches(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    mine = create_task_record(client, owner, "Mine", project_id=project_id)
    other = create_task_record(client, owner, "Other", project_id=project_id)
    r = client.post(
        f"{API}/tasks/{mine['id']}/comments/", headers=owner, json={"body": "Noted"}
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": [mine["id"], other["id"]], "priority": "P1"},
    )
    assert r.status_code == 200, r.text

    result = search_activity_body(db, caller, task_id=mine["id"])
    whats = _whats(result)
    assert "Created in" in "".join(whats)
    assert "Commented" in whats
    assert any(w.startswith("Changed 2 tasks") for w in whats)
    # Not the other task's own, unrelated creation.
    assert "Other" not in _titles(result)


def test_task_id_outside_scope_is_refused_the_way_the_api_refuses_it(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, "In scope")
    outside = create_project(client, owner, "Elsewhere")
    headers = bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Outside", project_id=outside)

    with pytest.raises(ToolError) as exc_info:
        search_activity_body(db, caller, task_id=task["id"])
    assert "not_found" in str(exc_info.value)


# project: one project's chronology


def test_project_narrows_to_its_own_chronology(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    other = create_project(client, owner, "Other")
    headers = bot_headers(
        client, owner, project_ids=[work, other], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    create_task_record(client, owner, "In Work", project_id=work)
    create_task_record(client, owner, "In Other", project_id=other)

    result = search_activity_body(db, caller, project="Work")
    titles = _titles(result)
    assert "In Work" in titles
    assert "In Other" not in titles


def test_project_outside_scope_is_refused_the_way_the_api_refuses_it(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, "In scope")
    outside = create_project(client, owner, "Elsewhere")
    headers = bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_activity_body(db, caller, project=outside)
    assert "not_found" in str(exc_info.value)


# actor: self, owner, any_bot, a named bot user


def test_actor_self_owner_any_bot_and_named_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    reader_user = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Reader",
    )
    reader = token_headers(client, owner, reader_user["id"])
    reader_caller = caller_for(db, reader)
    sibling_user = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Sibling",
    )
    sibling = token_headers(client, owner, sibling_user["id"])

    create_task_record(client, owner, "By the owner", project_id=project_id)
    create_task_record(client, sibling, "By the sibling", project_id=project_id)
    create_task_record(client, reader, "By the reader itself", project_id=project_id)

    assert _task_titles(search_activity_body(db, reader_caller, actor="self")) == [
        "By the reader itself"
    ]
    assert _task_titles(search_activity_body(db, reader_caller, actor="owner")) == [
        "By the owner"
    ]
    any_bot_titles = _task_titles(
        search_activity_body(db, reader_caller, actor="any_bot")
    )
    assert set(any_bot_titles) == {"By the sibling", "By the reader itself"}
    assert _task_titles(search_activity_body(db, reader_caller, actor="Sibling")) == [
        "By the sibling"
    ]
    assert _task_titles(
        search_activity_body(db, reader_caller, actor=sibling_user["id"])
    ) == ["By the sibling"]


def test_actor_unknown_bot_name_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_activity_body(db, caller, actor="No Such Bot")
    message = str(exc_info.value)
    assert "not_found" in message
    assert "No Such Bot" in message


def test_actor_ambiguous_bot_name_is_refused_with_matching_ids(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    first = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Agent",
    )
    second = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Agent",
    )
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Reader",
    )
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_activity_body(db, caller, actor="Agent")
    message = str(exc_info.value)
    assert "ambiguous_bot_name" in message
    assert first["id"] in message
    assert second["id"] in message


# since/until: a period with both bounds, and order


def test_since_and_until_bound_the_period_both_ways(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    create_task_record(client, owner, "Today's task", project_id=project_id)

    within = search_activity_body(
        db,
        caller,
        since=str(YESTERDAY),
        until=str(TODAY),
        kind=ActivityKind.CREATED,
    )
    assert "Today's task" in _titles(within)

    too_late_since = search_activity_body(
        db, caller, since=str(TOMORROW), kind=ActivityKind.CREATED
    )
    assert "Today's task" not in _titles(too_late_since)

    too_early_until = search_activity_body(
        db, caller, until=str(YESTERDAY), kind=ActivityKind.CREATED
    )
    assert "Today's task" not in _titles(too_early_until)


def test_order_newest_or_oldest_first(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    create_task_record(client, owner, "First", project_id=project_id)
    create_task_record(client, owner, "Second", project_id=project_id)

    newest = search_activity_body(db, caller, kind=ActivityKind.CREATED)
    assert _task_titles(newest) == ["Second", "First"]

    oldest = search_activity_body(
        db, caller, kind=ActivityKind.CREATED, order=ActivityOrder.OLDEST
    )
    assert _task_titles(oldest) == ["First", "Second"]


# A since-deleted task's history still reads, inviting no restore


def test_a_completion_of_a_since_deleted_task_still_reads(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(
        client, owner, "Finish then forget", project_id=project_id
    )
    r = client.patch(
        f"{API}/tasks/{task['id']}", headers=owner, json={"status": "done"}
    )
    assert r.status_code == 200, r.text
    assert delete_task(client, owner, task["id"]).status_code == 200

    result = search_activity_body(db, caller, kind=ActivityKind.COMPLETED)
    [row] = result["entries"]
    assert row["what"] == "Completed"
    assert row["subject"]["title"] == "Finish then forget"
    assert set(row) == {"at", "actor", "what", "subject"}


# "what" for the rest of the action vocabulary: each of these is its own
# branch in `_describe`/`_subject`, ported from `ActivityDescription.tsx`,
# so each gets its own fixture through the real API rather than trusting the
# port by inspection.


def test_task_moved_names_both_projects(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    from_project = create_project(client, owner, "From")
    to_project = create_project(client, owner, "To")
    headers = bot_headers(
        client,
        owner,
        project_ids=[from_project, to_project],
        permissions=ALL_PERMISSIONS,
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Movable", project_id=from_project)
    r = client.patch(
        f"{API}/tasks/{task['id']}", headers=owner, json={"project_id": to_project}
    )
    assert r.status_code == 200, r.text

    result = search_activity_body(
        db, caller, kind=ActivityKind.CHANGED, task_id=task["id"]
    )
    [row] = result["entries"]
    assert row["what"] == "Moved from From to To"
    assert row["subject"] == {
        "type": "task",
        "id": task["id"].replace("-", "")[:8],
        "title": "Movable",
    }


def test_task_assigned_and_unassigned_name_the_assignee(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    owner_id = client.get(f"{API}/caller", headers=owner).json()["actor"]["id"]
    task = create_task_record(client, owner, "Assign me", project_id=project_id)

    r = client.patch(
        f"{API}/tasks/{task['id']}", headers=owner, json={"assignee_id": owner_id}
    )
    assert r.status_code == 200, r.text
    r = client.patch(
        f"{API}/tasks/{task['id']}", headers=owner, json={"assignee_id": None}
    )
    assert r.status_code == 200, r.text

    result = search_activity_body(
        db, caller, kind=ActivityKind.CHANGED, task_id=task["id"]
    )
    whats = _whats(result)
    assert "Assigned to owner" in whats
    assert "Unassigned" in whats


def test_task_status_changed_between_open_statuses_and_reopened(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Call the bank", project_id=project_id)
    for status in ["in_progress", "done", "in_progress"]:
        r = client.patch(
            f"{API}/tasks/{task['id']}", headers=owner, json={"status": status}
        )
        assert r.status_code == 200, r.text

    result = search_activity_body(
        db, caller, task_id=task["id"], order=ActivityOrder.OLDEST
    )
    whats = _whats(result)
    assert "Moved to In progress" in whats
    assert "Completed" in whats
    assert "Reopened" in whats


def test_project_changed_deleted_and_restored(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Renamed later")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    r = client.patch(
        f"{API}/projects/{project_id}", headers=owner, json={"name": "New name"}
    )
    assert r.status_code == 200, r.text
    r = client.delete(f"{API}/projects/{project_id}", headers=owner)
    assert r.status_code == 200, r.text
    log = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    deleted_entry = next(e for e in log if e["action"] == "project_deleted")
    r = client.post(f"{API}/activity-log/{deleted_entry['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    # The bot's own scope is the project itself, which is gone and back again
    # by the time this reads — `project` can no longer name it to narrow by,
    # so this reads the bot's whole feed instead.
    result = search_activity_body(db, caller, order=ActivityOrder.OLDEST)
    whats = _whats(result)
    assert "Changed name" in whats
    assert "Deleted" in whats
    assert "Restored" in whats
    for row in result["entries"]:
        if row["subject"]["type"] == "project":
            assert row["subject"]["name"] in ("New name", "Renamed later")


def test_tag_renamed_merged_and_deleted(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    create_task_record(client, owner, "Tagged", project_id=project_id, tags=["wip"])
    tags = {
        t["name"]: t for t in client.get(f"{API}/tags/", headers=owner).json()["data"]
    }
    r = client.patch(
        f"{API}/tags/{tags['wip']['id']}", headers=owner, json={"name": "in-progress"}
    )
    assert r.status_code == 200, r.text

    create_task_record(client, owner, "Also tagged", project_id=project_id, tags=["x"])
    tags = {
        t["name"]: t for t in client.get(f"{API}/tags/", headers=owner).json()["data"]
    }
    r = client.post(
        f"{API}/tags/{tags['in-progress']['id']}/merge",
        headers=owner,
        json={"source_ids": [tags["x"]["id"]]},
    )
    assert r.status_code == 200, r.text

    create_task_record(
        client, owner, "Briefly tagged", project_id=project_id, tags=["z"]
    )
    tags = {
        t["name"]: t for t in client.get(f"{API}/tags/", headers=owner).json()["data"]
    }
    r = client.delete(f"{API}/tags/{tags['z']['id']}", headers=owner)
    assert r.status_code == 200, r.text

    result = search_activity_body(db, caller, kind=ActivityKind.TAGS)
    whats = _whats(result)
    assert any(w.startswith("Renamed from") for w in whats)
    assert any(w.startswith("Merged") for w in whats)
    assert "Deleted, removed from 1 task" in whats


def test_comment_edited_and_deleted(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Commented on", project_id=project_id)
    r = client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=owner, json={"body": "Draft"}
    )
    assert r.status_code == 200, r.text
    comment_id = r.json()["id"]
    r = client.patch(
        f"{API}/comments/{comment_id}", headers=owner, json={"body": "Final"}
    )
    assert r.status_code == 200, r.text
    r = client.delete(f"{API}/comments/{comment_id}", headers=owner)
    assert r.status_code == 200, r.text

    result = search_activity_body(
        db, caller, kind=ActivityKind.COMMENTS, task_id=task["id"]
    )
    whats = _whats(result)
    assert "Edited a comment" in whats
    assert "Deleted a comment" in whats
    for row in result["entries"]:
        assert row["subject"] == {
            "type": "task",
            "id": task["id"].replace("-", "")[:8],
            "title": "Commented on",
        }


def test_attachment_added_and_deleted(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Has a file", project_id=project_id)
    r = client.post(
        f"{API}/tasks/{task['id']}/attachments/",
        headers=owner,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 200, r.text
    attachment_id = r.json()["id"]
    r = client.delete(f"{API}/attachments/{attachment_id}", headers=owner)
    assert r.status_code == 200, r.text

    result = search_activity_body(
        db, caller, kind=ActivityKind.COMMENTS, task_id=task["id"]
    )
    whats = _whats(result)
    assert "Attached “notes.txt”" in whats
    assert "Removed “notes.txt”" in whats


def test_task_restored_after_delete(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(
        client, owner, "Back from the dead", project_id=project_id
    )
    assert delete_task(client, owner, task["id"]).status_code == 200
    log = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    deleted_entry = next(e for e in log if e["action"] == "task_deleted")
    r = client.post(f"{API}/activity-log/{deleted_entry['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    result = search_activity_body(
        db, caller, kind=ActivityKind.DELETED, task_id=task["id"]
    )
    whats = _whats(result)
    assert "Deleted" in whats
    assert "Restored" in whats
