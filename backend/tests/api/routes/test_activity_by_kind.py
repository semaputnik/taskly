"""
Reading the log narrowed to one kind of change.

The log records everything (FR-10.3), which is what makes it trustworthy and
what makes "what did I finish" hard to ask of it. `kind` groups the actions
the way a reader thinks about them, rather than exposing the action names the
log stores.

The grouping is the server's, not the client's, because one of the groups
cannot be expressed as a set of actions: completing tasks in a batch writes a
single bulk entry naming the new status, not a completion per task.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import create_project, create_task, create_user_headers

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _log(client: TestClient, headers: Headers, **params: Any) -> Any:
    r = client.get(f"{API}/activity-log/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _actions(page: Any) -> list[str]:
    return [entry["action"] for entry in page["data"]]


def _complete(client: TestClient, headers: Headers, task_id: str) -> None:
    r = client.patch(
        f"{API}/tasks/{task_id}", headers=headers, json={"status": "done"}
    )
    assert r.status_code == 200, r.text


def _complete_batch(client: TestClient, headers: Headers, task_ids: list[str]) -> None:
    r = client.post(
        f"{API}/tasks/bulk",
        headers=headers,
        json={"task_ids": task_ids, "status": "done"},
    )
    assert r.status_code == 200, r.text


# --- What each kind gathers ----------------------------------------------------


def test_completed_gathers_tasks_closed_one_at_a_time(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id, title="Ship it")
    _complete(client, owner, task_id)

    page = _log(client, owner, kind="completed")

    assert _actions(page) == ["task_completed"]
    assert page["count"] == 1


def test_completed_gathers_tasks_closed_in_a_batch(
    client: TestClient, owner: Headers
) -> None:
    """
    A batch is logged as the one act it was, not as each task it touched, so
    closing several tasks at once writes no completion entry at all. The
    filter meant to find finished work has to find them anyway.
    """
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"T{n}")
        for n in range(3)
    ]
    _complete_batch(client, owner, ids)

    page = _log(client, owner, kind="completed")

    assert _actions(page) == ["tasks_bulk_changed"]
    assert page["count"] == 1


def test_completed_leaves_out_a_batch_that_changed_something_else(
    client: TestClient, owner: Headers
) -> None:
    """A bulk entry is only a completion when the batch moved tasks to done."""
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"T{n}")
        for n in range(2)
    ]
    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": ids, "priority": "P1"},
    )
    assert r.status_code == 200, r.text

    assert _log(client, owner, kind="completed")["count"] == 0
    assert _log(client, owner, kind="changed")["count"] == 1


def test_completed_leaves_out_creations_and_reopenings(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    _complete(client, owner, task_id)
    r = client.patch(
        f"{API}/tasks/{task_id}", headers=owner, json={"status": "todo"}
    )
    assert r.status_code == 200, r.text

    assert _actions(_log(client, owner, kind="completed")) == ["task_completed"]


def test_created_gathers_tasks_and_projects(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Roadmap")
    create_task(client, owner, project_id=project_id)

    actions = _actions(_log(client, owner, kind="created"))

    assert set(actions) == {"task_created", "project_created"}


def test_deleted_gathers_deletions_and_restores(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    r = client.delete(f"{API}/tasks/{task_id}", headers=owner)
    assert r.status_code == 200, r.text

    page = _log(client, owner, kind="deleted")
    entry = page["data"][0]
    assert entry["action"] == "task_deleted"

    r = client.post(f"{API}/activity-log/{entry['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    assert set(_actions(_log(client, owner, kind="deleted"))) == {
        "task_deleted",
        "task_restored",
    }


def test_comments_gathers_comments_and_attachments(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    r = client.post(
        f"{API}/tasks/{task_id}/comments/", headers=owner, json={"body": "Noted"}
    )
    assert r.status_code == 200, r.text

    assert _actions(_log(client, owner, kind="comments")) == ["comment_added"]


def test_tags_gathers_tag_changes(client: TestClient, owner: Headers) -> None:
    r = client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    assert r.status_code == 200, r.text

    assert _actions(_log(client, owner, kind="tags")) == ["tag_created"]


# --- How the filter behaves ----------------------------------------------------


def test_no_kind_lists_everything(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    _complete(client, owner, task_id)

    everything = _log(client, owner)

    assert everything["count"] == 3
    assert set(_actions(everything)) == {
        "project_created",
        "task_created",
        "task_completed",
    }


def test_an_unknown_kind_is_refused(client: TestClient, owner: Headers) -> None:
    r = client.get(f"{API}/activity-log/", headers=owner, params={"kind": "nonsense"})
    assert r.status_code == 422


def test_the_count_is_the_narrowed_count(client: TestClient, owner: Headers) -> None:
    """Paging a narrowed log must page the narrowing, not the whole log."""
    project_id = create_project(client, owner)
    for n in range(3):
        task_id = create_task(client, owner, project_id=project_id, title=f"T{n}")
        _complete(client, owner, task_id)

    page = _log(client, owner, kind="completed", limit=2)

    assert page["count"] == 3
    assert len(page["data"]) == 2


def test_kind_combines_with_the_bot_user_filter(
    client: TestClient, db: Session, owner: Headers
) -> None:
    """
    Each narrowing holds on its own, and together they narrow further: what
    this integration finished, as opposed to what it did or what anyone
    finished.
    """
    from tests.utils.bot import ALL_PERMISSIONS, create_bot_user, token_headers

    project_id = create_project(client, owner)
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot = token_headers(client, owner, bot_user["id"])

    by_bot = create_task(client, bot, project_id=project_id, title="Bot's own")
    _complete(client, bot, by_bot)
    by_owner = create_task(client, owner, project_id=project_id, title="Mine")
    _complete(client, owner, by_owner)

    both = _log(client, owner, kind="completed", actor_bot_user_id=bot_user["id"])

    assert both["count"] == 1
    assert both["data"][0]["actor_bot_user_id"] == bot_user["id"]
    assert _log(client, owner, kind="completed")["count"] == 2


def test_a_completing_batch_is_a_completion_and_not_a_change(
    client: TestClient, owner: Headers
) -> None:
    """
    The kinds do not overlap, so the one entry a completing batch writes
    answers to Completed and to nothing else. A reader working through the
    groups meets it once.
    """
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"T{n}")
        for n in range(2)
    ]
    _complete_batch(client, owner, ids)

    assert _log(client, owner, kind="completed")["count"] == 1
    assert _log(client, owner, kind="changed")["count"] == 0


def test_every_action_belongs_to_exactly_one_kind() -> None:
    """
    A kind of entry that no group gathers is unreachable from the filter, and
    nothing about adding one would say so. This is the list that says so.
    """
    from app.api.routes.activity import _KIND_ACTIONS
    from app.models import ActivityAction, ActivityKind

    assert set(_KIND_ACTIONS) == set(ActivityKind)

    grouped = [action for actions in _KIND_ACTIONS.values() for action in actions]
    assert sorted(grouped) == sorted(ActivityAction), (
        "every action belongs to exactly one kind: add the new one to a group "
        "in _KIND_ACTIONS"
    )


def test_a_narrowed_log_stays_the_callers_own(
    client: TestClient, db: Session, owner: Headers
) -> None:
    """No filter widens the log past the caller's own entries (FR-10.7)."""
    stranger = create_user_headers(client, db)
    stranger_project = create_project(client, stranger, "Theirs")
    stranger_task = create_task(client, stranger, project_id=stranger_project)
    _complete(client, stranger, stranger_task)

    assert _log(client, owner, kind="completed")["count"] == 0
