"""
The four task statuses (semaputnik/taskly#97): what each move is allowed to
do, what it does to subtasks and series, and what the log says about it.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_project,
    create_user_headers,
    error_code,
    issue_bot_headers,
)

API = settings.API_V1_STR
STATUSES = ["todo", "in_progress", "waiting", "done"]
OPEN = ["todo", "in_progress", "waiting"]

Headers = dict[str, str]


def _create(client: TestClient, headers: Headers, **fields: Any) -> dict[str, Any]:
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": "T", **fields})
    assert r.status_code == 200, r.text
    task: dict[str, Any] = r.json()
    return task


def _patch(client: TestClient, headers: Headers, task_id: str, **fields: Any) -> Any:
    return client.patch(f"{API}/tasks/{task_id}", headers=headers, json=fields)


def _status(client: TestClient, headers: Headers, task_id: str) -> str:
    status: str = client.get(f"{API}/tasks/{task_id}", headers=headers).json()["status"]
    return status


def _tasks(client: TestClient, headers: Headers, **params: Any) -> list[dict[str, Any]]:
    r = client.get(f"{API}/tasks/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    data: list[dict[str, Any]] = r.json()["data"]
    return data


def _log(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    """The log, oldest first."""
    r = client.get(f"{API}/activity-log/", headers=headers)
    assert r.status_code == 200, r.text
    return list(reversed(r.json()["data"]))


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


# --- Creating -----------------------------------------------------------------


def test_a_new_task_is_to_do(client: TestClient, owner: Headers) -> None:
    assert _create(client, owner)["status"] == "todo"


def test_a_task_can_be_created_in_any_status(
    client: TestClient, owner: Headers
) -> None:
    for status in STATUSES:
        assert _create(client, owner, status=status)["status"] == status


def test_a_recurring_task_cannot_be_created_done(
    client: TestClient, owner: Headers
) -> None:
    r = client.post(
        f"{API}/tasks/",
        headers=owner,
        json={
            "title": "Water the plants",
            "due_date": "2026-03-01",
            "recurrence": {"frequency": "daily"},
            "status": "done",
        },
    )
    assert r.status_code == 400
    assert _tasks(client, owner) == []


def test_completed_is_no_longer_part_of_the_api(
    client: TestClient, owner: Headers
) -> None:
    task = _create(client, owner)
    assert "completed" not in task
    # Unknown fields are ignored, so the old flag changes nothing.
    r = _patch(client, owner, task["id"], completed=True)
    assert r.status_code == 200
    assert r.json()["status"] == "todo"


# --- Moving -------------------------------------------------------------------


@pytest.mark.parametrize("start", STATUSES)
@pytest.mark.parametrize("end", STATUSES)
def test_the_owner_can_make_every_move(
    client: TestClient, owner: Headers, start: str, end: str
) -> None:
    task = _create(client, owner, status=start)
    r = _patch(client, owner, task["id"], status=end)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == end


@pytest.mark.parametrize("start", STATUSES)
@pytest.mark.parametrize("end", STATUSES)
def test_a_bot_user_with_update_permission_can_make_every_move(
    client: TestClient, owner: Headers, start: str, end: str
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={"read_tasks": True, "update_tasks": True},
    )
    task = _create(client, owner, project_id=project_id, status=start)
    r = _patch(client, bot, task["id"], status=end)
    assert r.status_code == 200, r.text
    assert _status(client, owner, task["id"]) == end


def test_a_bot_user_without_update_permission_cannot_move_a_task(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions={"read_tasks": True}
    )
    task = _create(client, owner, project_id=project_id)
    assert _patch(client, bot, task["id"], status="in_progress").status_code == 403
    assert _status(client, owner, task["id"]) == "todo"


def test_an_unknown_status_is_refused(client: TestClient, owner: Headers) -> None:
    task = _create(client, owner)
    assert _patch(client, owner, task["id"], status="blocked").status_code == 422


# --- Subtasks -----------------------------------------------------------------


def _tree(client: TestClient, headers: Headers) -> tuple[str, str]:
    root = _create(client, headers, title="Root")
    child = _create(client, headers, title="Child", parent_id=root["id"])
    return root["id"], child["id"]


@pytest.mark.parametrize("open_status", OPEN)
def test_done_with_an_open_subtask_is_refused(
    client: TestClient, owner: Headers, open_status: str
) -> None:
    root, child = _tree(client, owner)
    assert _patch(client, owner, child, status=open_status).status_code == 200

    r = _patch(client, owner, root, status="done")
    assert r.status_code == 409
    assert error_code(r) == "task_has_uncompleted_subtasks"
    assert _status(client, owner, root) == "todo"


def test_done_leaving_subtasks_keeps_each_status(
    client: TestClient, owner: Headers
) -> None:
    root, child = _tree(client, owner)
    _patch(client, owner, child, status="waiting")

    r = _patch(client, owner, root, status="done", subtasks="leave_uncompleted")
    assert r.status_code == 200, r.text
    assert _status(client, owner, child) == "waiting"


def test_done_with_subtasks_moves_them_to_done(
    client: TestClient, owner: Headers
) -> None:
    root, child = _tree(client, owner)
    _patch(client, owner, child, status="in_progress")

    r = _patch(client, owner, root, status="done", subtasks="complete")
    assert r.status_code == 200, r.text
    assert _status(client, owner, child) == "done"


def test_a_done_subtree_does_not_block_done(client: TestClient, owner: Headers) -> None:
    root, child = _tree(client, owner)
    _patch(client, owner, child, status="done")
    assert _patch(client, owner, root, status="done").status_code == 200


@pytest.mark.parametrize("end", ["in_progress", "waiting", "todo"])
def test_moving_between_open_statuses_leaves_subtasks_alone(
    client: TestClient, owner: Headers, end: str
) -> None:
    root, child = _tree(client, owner)
    _patch(client, owner, root, status="in_progress")

    r = _patch(client, owner, root, status=end)
    assert r.status_code == 200, r.text
    assert _status(client, owner, child) == "todo"


def test_subtasks_only_goes_with_done(client: TestClient, owner: Headers) -> None:
    root, _ = _tree(client, owner)
    r = _patch(client, owner, root, status="in_progress", subtasks="complete")
    assert r.status_code == 400
    assert _status(client, owner, root) == "todo"


def test_closing_every_subtask_leaves_the_parent_open(
    client: TestClient, owner: Headers
) -> None:
    root, child = _tree(client, owner)
    _patch(client, owner, root, status="in_progress")
    _patch(client, owner, child, status="done")
    assert _status(client, owner, root) == "in_progress"


# --- Recurring tasks ----------------------------------------------------------


def _recurring(client: TestClient, headers: Headers) -> dict[str, Any]:
    return _create(
        client,
        headers,
        title="Water the plants",
        due_date="2026-03-01",
        recurrence={"frequency": "daily"},
    )


def _occurrences(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    return [t for t in _tasks(client, headers) if t["title"] == "Water the plants"]


@pytest.mark.parametrize("path", [["in_progress", "waiting", "todo"], ["waiting"]])
def test_open_moves_create_no_occurrence(
    client: TestClient, owner: Headers, path: list[str]
) -> None:
    task = _recurring(client, owner)
    for status in path:
        assert _patch(client, owner, task["id"], status=status).status_code == 200
    assert len(_occurrences(client, owner)) == 1


@pytest.mark.parametrize("start", OPEN)
def test_done_creates_exactly_one_to_do_occurrence(
    client: TestClient, owner: Headers, start: str
) -> None:
    task = _recurring(client, owner)
    _patch(client, owner, task["id"], status=start)

    assert _patch(client, owner, task["id"], status="done").status_code == 200

    occurrences = _occurrences(client, owner)
    assert len(occurrences) == 2
    successor = next(t for t in occurrences if t["id"] != task["id"])
    assert successor["status"] == "todo"
    assert successor["due_date"] == "2026-03-02"


@pytest.mark.parametrize("end", OPEN)
def test_only_the_latest_occurrence_can_leave_done(
    client: TestClient, owner: Headers, end: str
) -> None:
    task = _recurring(client, owner)
    _patch(client, owner, task["id"], status="done")

    r = _patch(client, owner, task["id"], status=end)
    assert r.status_code == 409
    assert error_code(r) == "occurrence_superseded"
    assert r.json()["detail"]["message"].endswith(
        "Only the latest occurrence can be reopened."
    )


def test_the_rule_changes_only_while_the_task_is_open(
    client: TestClient, owner: Headers
) -> None:
    task = _recurring(client, owner)
    _patch(client, owner, task["id"], status="waiting")
    r = _patch(client, owner, task["id"], recurrence={"frequency": "weekly"})
    assert r.status_code == 200, r.text

    _patch(client, owner, task["id"], status="done")
    r = _patch(client, owner, task["id"], recurrence={"frequency": "daily"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Only an open task can change how it recurs"


# --- Filtering ----------------------------------------------------------------


def test_the_status_filter_is_repeatable(client: TestClient, owner: Headers) -> None:
    ids = {status: _create(client, owner, status=status)["id"] for status in STATUSES}

    def listed(**params: Any) -> set[str]:
        return {t["id"] for t in _tasks(client, owner, **params)}

    assert listed(status="waiting") == {ids["waiting"]}
    assert listed(status=OPEN) == {ids[s] for s in OPEN}
    assert listed() == set(ids.values())


def test_overdue_leaves_done_out(client: TestClient, owner: Headers) -> None:
    late = {
        status: _create(client, owner, status=status, due_date="2020-01-01")["id"]
        for status in STATUSES
    }
    overdue = {t["id"] for t in _tasks(client, owner, overdue=True)}
    assert overdue == {late[s] for s in OPEN}


# --- Bulk ---------------------------------------------------------------------


def _bulk(client: TestClient, headers: Headers, **changes: Any) -> Any:
    return client.post(f"{API}/tasks/bulk", headers=headers, json=changes)


def test_bulk_sets_a_status(client: TestClient, owner: Headers) -> None:
    ids = [_create(client, owner)["id"] for _ in range(2)]
    r = _bulk(client, owner, task_ids=ids, status="waiting")
    assert r.status_code == 200, r.text
    assert [_status(client, owner, task_id) for task_id in ids] == [
        "waiting",
        "waiting",
    ]


def test_bulk_refuses_to_reopen_an_earlier_occurrence(
    client: TestClient, owner: Headers
) -> None:
    task = _recurring(client, owner)
    _patch(client, owner, task["id"], status="done")

    r = _bulk(client, owner, task_ids=[task["id"]], status="in_progress")
    assert r.status_code == 409
    [refusal] = r.json()["detail"]["refusals"]
    assert refusal["code"] == "occurrence_superseded"
    assert _status(client, owner, task["id"]) == "done"


def test_bulk_open_moves_ignore_open_subtasks(
    client: TestClient, owner: Headers
) -> None:
    root, child = _tree(client, owner)
    assert (
        _bulk(client, owner, task_ids=[root], status="in_progress").status_code == 200
    )
    assert _status(client, owner, child) == "todo"


def test_bulk_subtasks_only_goes_with_done(client: TestClient, owner: Headers) -> None:
    root, _ = _tree(client, owner)
    r = _bulk(client, owner, task_ids=[root], status="waiting", subtasks="complete")
    assert r.status_code == 400
    assert _status(client, owner, root) == "todo"


# --- Activity log -------------------------------------------------------------


def test_each_kind_of_move_is_logged_once(client: TestClient, owner: Headers) -> None:
    task = _create(client, owner, title="Call the bank")
    for status in ["in_progress", "waiting", "done", "in_progress"]:
        assert _patch(client, owner, task["id"], status=status).status_code == 200

    entries = [e for e in _log(client, owner) if e["action"] != "task_created"]
    assert [e["action"] for e in entries] == [
        "task_status_changed",
        "task_status_changed",
        "task_completed",
        "task_reopened",
    ]
    assert entries[0]["details"] == {
        "title": "Call the bank",
        "from": "todo",
        "to": "in_progress",
    }
    assert entries[1]["details"]["from"] == "in_progress"
    assert entries[1]["details"]["to"] == "waiting"
    assert entries[3]["details"]["to"] == "in_progress"


def test_the_creation_entry_records_the_status(
    client: TestClient, owner: Headers
) -> None:
    _create(client, owner, status="waiting")
    [entry] = _log(client, owner)
    assert entry["details"]["task"]["status"] == "waiting"


def test_a_bulk_status_change_is_one_entry(client: TestClient, owner: Headers) -> None:
    ids = [_create(client, owner)["id"] for _ in range(3)]
    seen = len(_log(client, owner))

    assert _bulk(client, owner, task_ids=ids, status="waiting").status_code == 200

    entries = _log(client, owner)[seen:]
    assert [e["action"] for e in entries] == ["tasks_bulk_changed"]
    assert entries[0]["details"]["changes"] == {"status": "waiting"}


def test_a_bots_move_is_attributed_to_it(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task = _create(client, owner, project_id=project_id)
    _patch(client, bot, task["id"], status="in_progress")

    entry = _log(client, owner)[-1]
    assert entry["action"] == "task_status_changed"
    assert entry["actor_bot_user_id"] is not None
