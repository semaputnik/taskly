"""
Reading one task's history: the log narrowed to a single task.

The task panel's Activity section is the task's own chronology, so the log has
to be able to answer "what happened to this task" without the client reading
the whole account's log and picking its lines out. The narrowing never widens
the log: it is the caller's own entries, filtered (FR-10.7), and a task that is
not the caller's is refused rather than read as an empty history.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_project,
    create_task,
    create_user_headers,
    delete_task,
    issue_bot_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _history(client: TestClient, headers: Headers, task_id: str, **params: Any) -> Any:
    r = client.get(
        f"{API}/activity-log/", headers=headers, params={"task_id": task_id, **params}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _actions(page: Any) -> list[str]:
    return [entry["action"] for entry in page["data"]]


def _comment(client: TestClient, headers: Headers, task_id: str, body: str) -> str:
    r = client.post(
        f"{API}/tasks/{task_id}/comments/", headers=headers, json={"body": body}
    )
    assert r.status_code == 200, r.text
    comment_id: str = r.json()["id"]
    return comment_id


def _attach(client: TestClient, headers: Headers, task_id: str) -> str:
    r = client.post(
        f"{API}/tasks/{task_id}/attachments/",
        headers=headers,
        files={"file": ("quote.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    attachment_id: str = r.json()["id"]
    return attachment_id


def test_the_filter_returns_the_tasks_own_entries_and_those_on_it(
    client: TestClient, owner: Headers
) -> None:
    task_id = create_task(client, owner, title="Fix the tap")
    other_id = create_task(client, owner, title="Mow the lawn")
    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"priority": "P1"})
    comment_id = _comment(client, owner, task_id, "Drips")
    attachment_id = _attach(client, owner, task_id)
    _comment(client, owner, other_id, "Not this one")
    _attach(client, owner, other_id)
    client.patch(f"{API}/comments/{comment_id}", headers=owner, json={"body": "Pours"})
    client.delete(f"{API}/attachments/{attachment_id}", headers=owner)
    client.delete(f"{API}/comments/{comment_id}", headers=owner)

    page = _history(client, owner, task_id)

    # Newest first, as the log is, and nothing of the other task in it.
    assert _actions(page) == [
        "comment_deleted",
        "attachment_deleted",
        "comment_edited",
        "attachment_added",
        "comment_added",
        "task_changed",
        "task_created",
    ]
    assert page["count"] == 7
    for entry in page["data"]:
        if entry["entity_type"] == "task":
            assert entry["entity_id"] == task_id
        else:
            assert entry["details"]["task"]["id"] == task_id


def test_a_batch_that_touched_the_task_is_in_its_history(
    client: TestClient, owner: Headers
) -> None:
    first = create_task(client, owner, title="First")
    second = create_task(client, owner, title="Second")
    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": [first, second], "priority": "P2"},
    )
    assert r.status_code == 200, r.text

    # The batch is one entry, named after the first task it touched; the
    # second one's history still has to show it happened.
    for task_id in (first, second):
        page = _history(client, owner, task_id)
        assert _actions(page) == ["tasks_bulk_changed", "task_created"]


def test_it_is_paged_like_the_log(client: TestClient, owner: Headers) -> None:
    task_id = create_task(client, owner)
    for index in range(4):
        _comment(client, owner, task_id, f"Note {index}")

    first = _history(client, owner, task_id, limit=2)
    later = _history(client, owner, task_id, skip=2, limit=2)
    rest = _history(client, owner, task_id, skip=4, limit=2)

    assert first["count"] == later["count"] == rest["count"] == 5
    seen = [e["id"] for page in (first, later, rest) for e in page["data"]]
    assert len(seen) == len(set(seen)) == 5
    assert _actions(rest) == ["task_created"]


def test_it_combines_with_the_kind(client: TestClient, owner: Headers) -> None:
    task_id = create_task(client, owner)
    _comment(client, owner, task_id, "Hello")
    _attach(client, owner, task_id)

    page = _history(client, owner, task_id, kind="comments")
    assert sorted(_actions(page)) == ["attachment_added", "comment_added"]
    assert _history(client, owner, task_id, kind="completed")["count"] == 0


def test_a_deleted_tasks_history_still_reads(
    client: TestClient, owner: Headers
) -> None:
    task_id = create_task(client, owner)
    assert delete_task(client, owner, task_id).status_code == 200

    page = _history(client, owner, task_id)
    assert _actions(page) == ["task_deleted", "task_created"]


def test_another_users_task_is_refused(
    client: TestClient, db: Session, owner: Headers
) -> None:
    task_id = create_task(client, owner)
    _comment(client, owner, task_id, "Private")
    other = create_user_headers(client, db)

    r = client.get(f"{API}/activity-log/", headers=other, params={"task_id": task_id})
    assert r.status_code == 404

    # A task that exists nowhere reads exactly the same.
    r = client.get(
        f"{API}/activity-log/", headers=other, params={"task_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404


def test_the_superuser_gains_no_reach_through_the_filter(
    client: TestClient, owner: Headers, superuser_token_headers: Headers
) -> None:
    task_id = create_task(client, owner)

    r = client.get(
        f"{API}/activity-log/",
        headers=superuser_token_headers,
        params={"task_id": task_id},
    )
    assert r.status_code == 404


def test_a_bot_user_cannot_read_a_tasks_history(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, bot, project_id=project_id)

    r = client.get(f"{API}/activity-log/", headers=bot, params={"task_id": task_id})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "human_only"


def test_the_bot_users_entries_name_it(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, bot, project_id=project_id)
    _comment(client, bot, task_id, "On it")

    page = _history(client, owner, task_id)
    assert [e["actor_bot_user_name"] for e in page["data"]] == [
        "Triage agent",
        "Triage agent",
    ]
