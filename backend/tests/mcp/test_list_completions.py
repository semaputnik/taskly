"""
`list_completions` (spec #247, #248, #260): finished work as a table, built
over a history the fixtures below write through the API the way #248's own
testing decision asks for — tasks created and closed on known dates, a batch
closing several at once, a task reopened and closed again, one deleted
afterwards, and a series' occurrences — then read back as rows and a
summary, never asserted by how they were counted.

The visibility rules themselves (the scope, the archive, the `read_activity`
grant) are #246's and tested there (`tests/api/routes/test_activity_for_bots.py`);
these tests are about this tool's own row-per-completion assembly, the
splits and the median, and the three traps spec #248 calls out: a batch
expanded into a row per task, a reopened task counted as two completions
over one task, and a deleted task's row carrying no current field.

Dates are not reachable through the API (a task's `created_at` and an
activity entry's `created_at` are both set by the server), so a fixture
that needs a known lead time sets them directly through the `db` session —
the same session `create_user_headers` itself writes a user through — after
the act that would otherwise stamp "now".

Exercised against `list_completions_body` directly (#302) — see
`test_whoami.py`'s own module docstring for why, and where the protocol
itself is still tested.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session, col, select

from app.core.config import settings
from app.mcp.tools.list_completions import list_completions_body
from app.models import ActivityAction, ActivityEntry, Task
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_recurring_task,
    create_task_record,
    create_user_headers,
    delete_task,
    token_headers,
)
from tests.utils.mcp import bot_headers
from tests.utils.mcp_body import caller_for

API = settings.API_V1_STR
TODAY = date.today()
SINCE = str(TODAY - timedelta(days=30))
UNTIL = str(TODAY)

Headers = dict[str, str]


def _at(days_ago: int) -> datetime:
    """A moment `days_ago` days before today, at midnight UTC — exact enough for a day-based lead time."""
    return datetime.combine(TODAY - timedelta(days=days_ago), time.min, tzinfo=UTC)


def _backdate_task(db: Session, task_id: str, when: datetime) -> None:
    """A task's own `filed` moment, set directly: the API only ever files one as of now."""
    task = db.get(Task, uuid.UUID(task_id))
    assert task is not None
    task.created_at = when
    db.add(task)
    db.commit()


def _backdate_completion(
    db: Session, task_id: str, when: datetime, *, nth: int = -1
) -> None:
    """
    The `nth` `task_completed` entry for this task (default the last), set
    directly to a known `closed` moment — `nth` picks one of two when a task
    was closed, reopened and closed again.
    """
    entries = db.exec(
        select(ActivityEntry)
        .where(
            ActivityEntry.entity_id == uuid.UUID(task_id),
            ActivityEntry.action == ActivityAction.TASK_COMPLETED,
        )
        .order_by(col(ActivityEntry.position))
    ).all()
    entry = entries[nth]
    entry.created_at = when
    db.add(entry)
    db.commit()


def _backdate_batch(db: Session, task_ids: list[str], when: datetime) -> None:
    """The one `tasks_bulk_changed` entry naming exactly these tasks, backdated to a known `closed` moment."""
    wanted = set(task_ids)
    entries = db.exec(
        select(ActivityEntry).where(
            ActivityEntry.action == ActivityAction.TASKS_BULK_CHANGED
        )
    ).all()
    [entry] = [e for e in entries if set(e.details.get("task_ids", [])) == wanted]
    entry.created_at = when
    db.add(entry)
    db.commit()


def _complete(client: TestClient, headers: Headers, task_id: str) -> None:
    r = client.patch(f"{API}/tasks/{task_id}", headers=headers, json={"status": "done"})
    assert r.status_code == 200, r.text


def _rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result["completions"]
    assert isinstance(rows, list)
    return rows


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
        list_completions_body(db, caller, since=SINCE, until=UNTIL)
    message = str(exc_info.value)
    assert "permission_not_granted" in message
    assert "activity log" in message


def test_a_single_completion_row_with_known_lead_time(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(
        client,
        owner,
        "Write the report",
        project_id=project_id,
        priority="P2",
        tags=["writing"],
    )
    _complete(client, owner, task["id"])
    _backdate_task(db, task["id"], _at(5))
    _backdate_completion(db, task["id"], _at(2))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    [row] = _rows(result)
    assert row["id"] == task["id"].replace("-", "")[:8]
    assert row["title"] == "Write the report"
    assert row["project"] == "Work"
    assert row["tags"] == ["writing"]
    assert row["priority"] == "P2"
    assert row["filed"] == _at(5).isoformat()
    assert row["closed"] == _at(2).isoformat()
    assert row["days_to_close"] == 3.0
    assert row["closed_by"] == "owner"
    assert "deleted" not in row

    assert result["count"] == 1
    assert result["summary"]["completions"] == 1
    assert result["summary"]["distinct_tasks"] == 1
    assert result["summary"]["by_project"] == {"Work": 1}
    assert result["summary"]["by_actor"] == {"owner": 1}
    assert result["summary"]["median_days_to_close"] == 3.0


def test_a_batch_completion_produces_a_row_per_task(
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
    third = create_task_record(client, owner, "Third", project_id=project_id)
    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": [first["id"], second["id"], third["id"]], "status": "done"},
    )
    assert r.status_code == 200, r.text
    ids = [first["id"], second["id"], third["id"]]
    _backdate_batch(db, ids, _at(1))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    rows = _rows(result)
    assert len(rows) == 3
    assert {row["title"] for row in rows} == {"First", "Second", "Third"}
    assert all(row["closed"] == _at(1).isoformat() for row in rows)
    assert result["summary"]["completions"] == 3
    assert result["summary"]["distinct_tasks"] == 3


def test_a_reopened_and_reclosed_task_is_two_completions_of_one_task(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Flaky", project_id=project_id)

    _complete(client, owner, task["id"])
    _backdate_completion(db, task["id"], _at(10))
    r = client.patch(
        f"{API}/tasks/{task['id']}", headers=owner, json={"status": "todo"}
    )
    assert r.status_code == 200, r.text
    _complete(client, owner, task["id"])
    _backdate_completion(db, task["id"], _at(1))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    rows = _rows(result)
    assert len(rows) == 2
    assert {row["closed"] for row in rows} == {_at(10).isoformat(), _at(1).isoformat()}
    assert result["summary"]["completions"] == 2
    assert result["summary"]["distinct_tasks"] == 1


def test_a_deleted_task_keeps_its_row_marked_deleted_with_no_current_fields(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Work")
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(
        client,
        owner,
        "Finish then forget",
        project_id=project_id,
        priority="P1",
        tags=["temp"],
    )
    _complete(client, owner, task["id"])
    _backdate_task(db, task["id"], _at(8))
    _backdate_completion(db, task["id"], _at(4))
    assert delete_task(client, owner, task["id"]).status_code == 200

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    [row] = _rows(result)
    assert row["deleted"] is True
    assert row["title"] == "Finish then forget"
    assert row["project"] is None
    assert row["tags"] == []
    assert row["priority"] is None
    assert row["filed"] is None
    assert row["days_to_close"] is None
    assert row["closed"] == _at(4).isoformat()
    assert result["summary"]["by_project"] == {"(deleted)": 1}


def test_a_batch_closed_task_later_deleted_falls_back_to_untitled(
    client: TestClient, db: Session
) -> None:
    """
    A batch entry names no titles at all (`app.activity._write` records only
    `task_ids`), so a task closed that way and since deleted has nothing of
    its own completion entry to fall back on — this is the one row that
    reads "Untitled task" rather than a title the entry never recorded.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    task = create_task_record(client, owner, "Batched then gone", project_id=project_id)
    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": [task["id"]], "status": "done"},
    )
    assert r.status_code == 200, r.text
    _backdate_batch(db, [task["id"]], _at(1))
    assert delete_task(client, owner, task["id"]).status_code == 200

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    [row] = _rows(result)
    assert row["deleted"] is True
    assert row["title"] == "Untitled task"


def test_each_occurrence_of_a_series_is_its_own_completion(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    first = create_recurring_task(client, owner, TODAY, project_id=project_id)
    _complete(client, owner, first["id"])
    _backdate_completion(db, first["id"], _at(5))

    log = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    created = [
        e
        for e in log
        if e["action"] == "task_created" and e["entity_id"] != first["id"]
    ]
    [second_created] = created
    second_id = second_created["entity_id"]
    _complete(client, owner, second_id)
    _backdate_completion(db, second_id, _at(1))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    rows = _rows(result)
    assert len(rows) == 2
    assert {row["id"] for row in rows} == {
        first["id"].replace("-", "")[:8],
        second_id.replace("-", "")[:8],
    }
    assert result["summary"]["distinct_tasks"] == 2


def test_narrowing_by_project(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    home = create_project(client, owner, "Home")
    headers = bot_headers(
        client, owner, project_ids=[work, home], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    in_work = create_task_record(client, owner, "In Work", project_id=work)
    in_home = create_task_record(client, owner, "In Home", project_id=home)
    _complete(client, owner, in_work["id"])
    _complete(client, owner, in_home["id"])
    _backdate_completion(db, in_work["id"], _at(1))
    _backdate_completion(db, in_home["id"], _at(1))

    result = list_completions_body(
        db, caller, since=SINCE, until=UNTIL, project="Work"
    )
    rows = _rows(result)
    assert [row["title"] for row in rows] == ["In Work"]
    assert result["summary"]["completions"] == 1


def test_narrowing_by_actor(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    sibling = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Sibling",
    )
    sibling_headers = token_headers(client, owner, sibling["id"])
    headers = bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Reader",
    )
    caller = caller_for(db, headers)
    by_owner = create_task_record(client, owner, "By owner", project_id=project_id)
    by_sibling = create_task_record(
        client, sibling_headers, "By sibling", project_id=project_id
    )
    _complete(client, owner, by_owner["id"])
    _complete(client, sibling_headers, by_sibling["id"])
    _backdate_completion(db, by_owner["id"], _at(1))
    _backdate_completion(db, by_sibling["id"], _at(1))

    result = list_completions_body(
        db, caller, since=SINCE, until=UNTIL, actor="Sibling"
    )
    rows = _rows(result)
    assert [row["title"] for row in rows] == ["By sibling"]
    assert [row["closed_by"] for row in rows] == ["Sibling"]


def test_narrowing_by_tag(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    tagged = create_task_record(
        client, owner, "Tagged", project_id=project_id, tags=["urgent"]
    )
    untagged = create_task_record(client, owner, "Untagged", project_id=project_id)
    _complete(client, owner, tagged["id"])
    _complete(client, owner, untagged["id"])
    _backdate_completion(db, tagged["id"], _at(1))
    _backdate_completion(db, untagged["id"], _at(1))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL, tag="urgent")
    rows = _rows(result)
    assert [row["title"] for row in rows] == ["Tagged"]


def test_summary_splits_add_up_to_total_and_median_is_the_middle_value(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, "Work")
    home = create_project(client, owner, "Home")
    headers = bot_headers(
        client, owner, project_ids=[work, home], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    two_days = create_task_record(client, owner, "Two days", project_id=work)
    four_days = create_task_record(client, owner, "Four days", project_id=work)
    six_days = create_task_record(client, owner, "Six days", project_id=home)
    for task, filed_days_ago, closed_days_ago in (
        (two_days, 3, 1),
        (four_days, 5, 1),
        (six_days, 7, 1),
    ):
        _complete(client, owner, task["id"])
        _backdate_task(db, task["id"], _at(filed_days_ago))
        _backdate_completion(db, task["id"], _at(closed_days_ago))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    summary = result["summary"]
    assert summary["completions"] == 3
    assert sum(summary["by_project"].values()) == 3
    assert summary["by_project"] == {"Work": 2, "Home": 1}
    assert sum(summary["by_actor"].values()) == 3
    assert summary["median_days_to_close"] == 4.0


def test_truncated_names_a_filter_to_narrow_with(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    for i in range(3):
        task = create_task_record(client, owner, f"Task {i}", project_id=project_id)
        _complete(client, owner, task["id"])
        _backdate_completion(db, task["id"], _at(1))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL, limit=2)
    assert result["count"] == 3
    assert len(result["completions"]) == 2
    assert result["truncated"] is True
    assert result["narrow_with"] == "project"
    # The summary still covers every completion, not only the page.
    assert result["summary"]["completions"] == 3


def test_a_completion_outside_the_bot_users_scope_is_never_counted(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, "In scope")
    outside = create_project(client, owner, "Elsewhere")
    headers = bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)
    reachable = create_task_record(client, owner, "Reachable", project_id=in_scope)
    unreachable = create_task_record(client, owner, "Unreachable", project_id=outside)
    _complete(client, owner, reachable["id"])
    _complete(client, owner, unreachable["id"])
    _backdate_completion(db, reachable["id"], _at(1))
    _backdate_completion(db, unreachable["id"], _at(1))

    result = list_completions_body(db, caller, since=SINCE, until=UNTIL)
    rows = _rows(result)
    assert [row["title"] for row in rows] == ["Reachable"]
    assert result["summary"]["completions"] == 1


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
        list_completions_body(db, caller, since=SINCE, until=UNTIL, project=outside)
    assert "not_found" in str(exc_info.value)
