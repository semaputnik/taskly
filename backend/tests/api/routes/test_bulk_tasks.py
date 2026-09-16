"""
Changing many tasks at once: the sweep a triage surface needs.

A batch is one act, so it is one request, one transaction, one entry in the
activity log, and — where the act can be undone — one thing to restore. It is
the user's own act too: the endpoint takes a human caller, because batch
editing hands an agent far more leverage than the per-task endpoint it already
has (semaputnik/taskly#7's posture).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_project,
    create_task,
    create_user_headers,
    error_code,
    issue_bot_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _bulk(client: TestClient, headers: Headers, **body: Any) -> Any:
    return client.post(f"{API}/tasks/bulk", headers=headers, json=body)


def _bulk_delete(client: TestClient, headers: Headers, **body: Any) -> Any:
    return client.post(f"{API}/tasks/bulk-delete", headers=headers, json=body)


def _task(client: TestClient, headers: Headers, task_id: str) -> Any:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _titles(client: TestClient, headers: Headers, **params: Any) -> list[str]:
    r = client.get(f"{API}/tasks/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return [task["title"] for task in r.json()["data"]]


def _log(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    return client.get(f"{API}/activity-log/", headers=headers).json()["data"]


def _refusals(response: Any) -> dict[str, str]:
    """Which tasks the batch refused, and why, keyed by task id."""
    return {
        refusal["task_id"]: refusal["code"]
        for refusal in response.json()["detail"]["refusals"]
    }


# --- One change, many tasks ----------------------------------------------------


def test_a_batch_applies_one_change_to_every_task_named(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"Task {index}")
        for index in range(3)
    ]
    untouched = create_task(client, owner, project_id=project_id, title="Not in it")

    r = _bulk(client, owner, task_ids=ids, priority="P1")
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 3

    for task_id in ids:
        assert _task(client, owner, task_id)["priority"] == "P1"
    assert _task(client, owner, untouched)["priority"] is None


def test_a_batch_sets_tags_due_dates_and_assignees(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"Task {index}")
        for index in range(2)
    ]
    client.patch(f"{API}/tasks/{ids[0]}", headers=owner, json={"tags": ["keep"]})

    r = _bulk(
        client,
        owner,
        task_ids=ids,
        due_date="2026-12-01",
        add_tags=["swept"],
    )
    assert r.status_code == 200, r.text

    for task_id in ids:
        task = _task(client, owner, task_id)
        assert task["due_date"] == "2026-12-01"
        assert "swept" in task["tags"]
    # A tag a batch adds does not take away the ones a task already had.
    assert "keep" in _task(client, owner, ids[0])["tags"]

    r = _bulk(client, owner, task_ids=ids, remove_tags=["swept"])
    assert r.status_code == 200, r.text
    assert _task(client, owner, ids[0])["tags"] == ["keep"]
    assert _task(client, owner, ids[1])["tags"] == []


def test_a_batch_completes_and_moves(client: TestClient, owner: Headers) -> None:
    from_project = create_project(client, owner, "From")
    to_project = create_project(client, owner, "To")
    ids = [
        create_task(client, owner, project_id=from_project, title=f"Task {index}")
        for index in range(2)
    ]

    assert _bulk(client, owner, task_ids=ids, project_id=to_project).status_code == 200
    assert sorted(_titles(client, owner, project_id=to_project)) == [
        "Task 0",
        "Task 1",
    ]

    assert _bulk(client, owner, task_ids=ids, completed=True).status_code == 200
    assert all(_task(client, owner, task_id)["completed"] for task_id in ids)


# --- Whose tasks, and which of them ---------------------------------------------


def test_a_batch_never_reaches_another_users_task(
    client: TestClient, db: Session, owner: Headers
) -> None:
    mine = create_task(client, owner, title="Mine")
    other = create_user_headers(client, db)
    theirs = create_task(client, other, title="Theirs")

    r = _bulk(client, owner, task_ids=[mine, theirs], priority="P1")
    assert r.status_code == 409, r.text
    assert error_code(r) == "bulk_refused"
    assert _refusals(r) == {theirs: "not_found"}

    # All or nothing: the task it could have changed is untouched.
    assert _task(client, owner, mine)["priority"] is None
    assert _task(client, other, theirs)["priority"] is None


def test_a_batch_is_all_or_nothing(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    root = create_task(client, owner, project_id=project_id, title="Root")
    subtask = create_task(client, owner, parent_id=root, title="Subtask")
    elsewhere = create_project(client, owner, "Elsewhere")

    # A subtask holds no project of its own: it follows its root (FR-02.4).
    r = _bulk(client, owner, task_ids=[root, subtask], project_id=elsewhere)
    assert r.status_code == 409, r.text
    assert _refusals(r) == {subtask: "subtask_follows_parent"}
    assert (
        r.json()["detail"]["refusals"][0]["message"]
        == "A subtask follows the project of the task at the top of its tree."
    )
    # The root, which could have moved, did not.
    assert _task(client, owner, root)["project_id"] == project_id


def test_a_batch_refuses_an_archived_project_at_either_end(
    client: TestClient, owner: Headers
) -> None:
    live = create_project(client, owner, "Live")
    shelved = create_project(client, owner, "Shelved")
    task_id = create_task(client, owner, project_id=live, title="Task")
    frozen = create_task(client, owner, project_id=shelved, title="Frozen")
    client.post(f"{API}/projects/{shelved}/archive", headers=owner)

    # Moving into the archive is one fact about the request, not about each
    # task, so it is refused as the single-task move is.
    r = _bulk(client, owner, task_ids=[task_id], project_id=shelved)
    assert r.status_code == 409
    assert error_code(r) == "project_archived"

    r = _bulk(client, owner, task_ids=[frozen], priority="P1")
    assert r.status_code == 409
    assert _refusals(r) == {frozen: "project_archived"}


def test_a_batch_refuses_completing_a_task_with_open_subtasks(
    client: TestClient, owner: Headers
) -> None:
    root = create_task(client, owner, title="Root")
    create_task(client, owner, parent_id=root, title="Subtask")

    r = _bulk(client, owner, task_ids=[root], completed=True)
    assert r.status_code == 409
    assert _refusals(r) == {root: "task_has_uncompleted_subtasks"}

    # Saying what happens to them lets the batch through.
    r = _bulk(client, owner, task_ids=[root], completed=True, subtasks="complete")
    assert r.status_code == 200, r.text
    assert _task(client, owner, root)["completed"] is True


def test_a_bot_user_cannot_change_tasks_in_a_batch(
    client: TestClient, owner: Headers
) -> None:
    """
    Batch editing is leverage a bot user is not given: the endpoint takes a
    human, so no scope can reach it (FR-07.3's posture, semaputnik/taskly#7).
    """
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id, title="Task")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    r = _bulk(client, bot, task_ids=[task_id], priority="P1")
    assert r.status_code == 403
    assert error_code(r) == "human_only"
    assert _task(client, owner, task_id)["priority"] is None


# --- What the log says about a batch ---------------------------------------------


def test_a_batch_is_one_entry_in_the_log(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"Task {index}")
        for index in range(3)
    ]
    before = len(_log(client, owner))

    assert _bulk(client, owner, task_ids=ids, priority="P2").status_code == 200

    entries = _log(client, owner)
    assert len(entries) == before + 1
    entry = entries[0]
    assert entry["action"] == "tasks_bulk_changed"
    assert entry["details"]["task_count"] == 3
    assert entry["details"]["changes"]["priority"] == "P2"


def test_a_batch_deletion_is_one_entry_and_one_restore(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"Task {index}")
        for index in range(3)
    ]
    kept = create_task(client, owner, project_id=project_id, title="Kept")

    r = _bulk_delete(client, owner, task_ids=ids)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 3
    assert _titles(client, owner) == ["Kept"]

    entries = _log(client, owner)
    deletions = [e for e in entries if e["action"] == "task_deleted"]
    assert len(deletions) == 1
    assert deletions[0]["details"]["task_count"] == 3
    assert deletions[0]["restorable"] is True

    # One act, one undo: the three come back together and the fourth is
    # untouched (FR-10.4).
    r = client.post(f"{API}/activity-log/{deletions[0]['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text
    assert sorted(_titles(client, owner)) == ["Kept", "Task 0", "Task 1", "Task 2"]
    assert kept


def test_a_batch_deletion_takes_subtasks_only_when_told(
    client: TestClient, owner: Headers
) -> None:
    root = create_task(client, owner, title="Root")
    create_task(client, owner, parent_id=root, title="Subtask")

    r = _bulk_delete(client, owner, task_ids=[root])
    assert r.status_code == 409
    assert _refusals(r) == {root: "task_has_subtasks"}
    assert sorted(_titles(client, owner)) == ["Root", "Subtask"]

    r = _bulk_delete(client, owner, task_ids=[root], delete_subtasks=True)
    assert r.status_code == 200, r.text
    assert _titles(client, owner) == []


# --- Paging and sorting, at a size bigger than a page ----------------------------


def test_paging_a_sorted_list_is_complete_and_has_no_repeats(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    for index in range(12):
        client.post(
            f"{API}/tasks/",
            headers=owner,
            json={
                "title": f"Task {index:02d}",
                "project_id": project_id,
                "due_date": f"2026-01-{index + 1:02d}",
            },
        )

    seen: list[str] = []
    for page in range(3):
        r = client.get(
            f"{API}/tasks/",
            headers=owner,
            params={"skip": page * 5, "limit": 5, "sort": "due_date"},
        )
        assert r.json()["count"] == 12
        seen.extend(task["title"] for task in r.json()["data"])

    assert seen == [f"Task {index:02d}" for index in range(12)]
    assert len(set(seen)) == 12


def test_the_count_follows_the_filters_not_the_page(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    other_project = create_project(client, owner, "Other")
    for index in range(7):
        create_task(client, owner, project_id=project_id, title=f"In {index}")
    create_task(client, owner, project_id=other_project, title="Out")

    r = client.get(
        f"{API}/tasks/",
        headers=owner,
        params={"project_id": project_id, "skip": 0, "limit": 3},
    )
    assert r.json()["count"] == 7
    assert len(r.json()["data"]) == 3


def test_a_batch_that_completes_a_recurring_task_moves_its_series_on(
    client: TestClient, owner: Headers
) -> None:
    """
    A batch completes exactly as a single task does, so a series is never
    left with no open occurrence (FR-01.14).
    """
    project_id = create_project(client, owner)
    r = client.post(
        f"{API}/tasks/",
        headers=owner,
        json={
            "title": "Water the plants",
            "project_id": project_id,
            "due_date": "2026-03-02",
            "recurrence": {"frequency": "weekly"},
        },
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]

    assert _bulk(client, owner, task_ids=[task_id], completed=True).status_code == 200

    open_ones = [
        task
        for task in client.get(f"{API}/tasks/", headers=owner).json()["data"]
        if task["title"] == "Water the plants" and not task["completed"]
    ]
    assert len(open_ones) == 1
    assert open_ones[0]["due_date"] == "2026-03-09"


def test_restoring_a_batch_is_recorded_as_its_own_act(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"Task {index}")
        for index in range(2)
    ]
    assert _bulk_delete(client, owner, task_ids=ids).status_code == 200
    deletion = next(e for e in _log(client, owner) if e["action"] == "task_deleted")

    r = client.post(f"{API}/activity-log/{deletion['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    restored = [e for e in _log(client, owner) if e["action"] == "task_restored"]
    assert len(restored) == 1
    assert restored[0]["details"]["task_count"] == 2


def test_a_batch_counts_the_tasks_that_were_selected(
    client: TestClient, owner: Headers
) -> None:
    """
    Completing a task takes its subtasks with it, and they are part of the
    same act — not tasks the reader picked, and not counted as if they were.
    """
    root = create_task(client, owner, title="Root")
    create_task(client, owner, parent_id=root, title="Subtask")

    r = _bulk(client, owner, task_ids=[root], completed=True, subtasks="complete")
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 1

    entry = next(e for e in _log(client, owner) if e["action"] == "tasks_bulk_changed")
    assert entry["details"]["task_count"] == 1


def test_a_batch_delete_collects_an_archived_task_as_a_refusal(
    client: TestClient, owner: Headers
) -> None:
    live = create_project(client, owner, "Live")
    shelved = create_project(client, owner, "Shelved")
    task_id = create_task(client, owner, project_id=live, title="Task")
    frozen = create_task(client, owner, project_id=shelved, title="Frozen")
    client.post(f"{API}/projects/{shelved}/archive", headers=owner)

    r = _bulk_delete(client, owner, task_ids=[task_id, frozen], delete_subtasks=True)
    assert r.status_code == 409, r.text
    assert error_code(r) == "bulk_refused"
    assert _refusals(r) == {frozen: "project_archived"}
    # All or nothing, here too.
    assert sorted(_titles(client, owner)) == ["Task"]
