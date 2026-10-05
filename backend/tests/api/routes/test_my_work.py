"""
My work (FR-06.7, semaputnik/taskly#138): the tasks on the user themselves,
grouped by status, and the hand-over a bot user made by moving one to Review.
"""

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    create_bot_user,
    create_project,
    create_user_headers,
    my_id,
    token_headers,
)

API = settings.API_V1_STR
MY_WORK = ["in_progress", "review", "todo", "waiting"]

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _create(client: TestClient, headers: Headers, **fields: Any) -> dict[str, Any]:
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": "T", **fields})
    assert r.status_code == 200, r.text
    task: dict[str, Any] = r.json()
    return task


def _move(client: TestClient, headers: Headers, task_id: str, status: str) -> None:
    r = client.patch(f"{API}/tasks/{task_id}", headers=headers, json={"status": status})
    assert r.status_code == 200, r.text


def _bulk_move(client: TestClient, headers: Headers, task_id: str, status: str) -> None:
    r = client.post(
        f"{API}/tasks/bulk",
        headers=headers,
        json={"task_ids": [task_id], "status": status},
    )
    assert r.status_code == 200, r.text


def _shown(client: TestClient, headers: Headers, task_id: str) -> dict[str, Any]:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    task: dict[str, Any] = r.json()
    return task


@pytest.fixture
def agent(client: TestClient, owner: Headers) -> dict[str, Any]:
    """A bot user that may work on the tasks of one project, and that project."""
    project_id = create_project(client, owner, name="Research")
    bot = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions={"create_tasks": True, "read_tasks": True, "update_tasks": True},
        name="research-agent",
    )
    return {
        "id": bot["id"],
        "project_id": project_id,
        "headers": token_headers(client, owner, bot["id"]),
    }


# --- The panel's request -------------------------------------------------------


def test_my_work_lists_only_what_is_on_the_user_most_pressing_first(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    me = my_id(client, owner)
    _create(
        client, owner, title="Mine, P3", assignee_id=me, status="todo", priority="P3"
    )
    _create(
        client, owner, title="Mine, P1", assignee_id=me, status="todo", priority="P1"
    )
    _create(client, owner, title="Mine, review", assignee_id=me, status="review")
    _create(client, owner, title="Mine, waiting", assignee_id=me, status="waiting")
    _create(client, owner, title="Mine, backlog", assignee_id=me, status="backlog")
    _create(client, owner, title="Mine, done", assignee_id=me, status="done")
    _create(client, owner, title="Nobody's", status="todo")
    _create(
        client,
        owner,
        title="The agent's",
        project_id=agent["project_id"],
        assignee_id=agent["id"],
        status="in_progress",
    )

    def titles(status: list[str]) -> list[str]:
        r = client.get(
            f"{API}/tasks/",
            headers=owner,
            params={"assignee_id": me, "status": status, "sort": "priority"},
        )
        assert r.status_code == 200, r.text
        return [task["title"] for task in r.json()["data"]]

    assert titles(["todo"]) == ["Mine, P1", "Mine, P3"]
    assert titles(["in_progress"]) == []
    assert set(titles(MY_WORK)) == {
        "Mine, P1",
        "Mine, P3",
        "Mine, review",
        "Mine, waiting",
    }


# --- The hand-over -------------------------------------------------------------


def test_a_bot_users_move_to_review_is_its_hand_over(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(client, owner, project_id=agent["project_id"], status="in_progress")
    before = datetime.now().astimezone()

    _move(client, agent["headers"], task["id"], "review")

    handover = _shown(client, owner, task["id"])["handover"]
    assert handover["bot_user"] == {
        "id": agent["id"],
        "name": "research-agent",
        "deleted": False,
    }
    assert datetime.fromisoformat(handover["at"]) >= before


def test_a_task_a_bot_user_files_in_review_is_handed_over(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(
        client, agent["headers"], project_id=agent["project_id"], status="review"
    )

    assert (
        _shown(client, owner, task["id"])["handover"]["bot_user"]["id"] == agent["id"]
    )


def test_a_bot_user_reopening_a_task_into_review_hands_it_over(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(client, owner, project_id=agent["project_id"], status="done")

    _move(client, agent["headers"], task["id"], "review")

    assert (
        _shown(client, owner, task["id"])["handover"]["bot_user"]["id"] == agent["id"]
    )


def test_the_user_moving_a_task_to_review_hands_nothing_over(
    client: TestClient, owner: Headers
) -> None:
    task = _create(client, owner, status="in_progress")
    _move(client, owner, task["id"], "review")
    assert _shown(client, owner, task["id"])["handover"] is None


def test_only_the_latest_move_to_review_counts(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(client, owner, project_id=agent["project_id"], status="in_progress")
    _move(client, agent["headers"], task["id"], "review")
    _move(client, owner, task["id"], "in_progress")
    _move(client, owner, task["id"], "review")

    assert _shown(client, owner, task["id"])["handover"] is None


def test_a_batch_move_by_the_user_counts_as_theirs(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(client, owner, project_id=agent["project_id"], status="in_progress")
    _move(client, agent["headers"], task["id"], "review")
    _bulk_move(client, owner, task["id"], "in_progress")
    _bulk_move(client, owner, task["id"], "review")

    assert _shown(client, owner, task["id"])["handover"] is None


def test_a_task_out_of_review_has_no_hand_over(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(client, owner, project_id=agent["project_id"], status="in_progress")
    _move(client, agent["headers"], task["id"], "review")
    _move(client, owner, task["id"], "todo")

    assert _shown(client, owner, task["id"])["handover"] is None


def test_other_changes_after_the_hand_over_keep_it(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    me = my_id(client, owner)
    task = _create(client, owner, project_id=agent["project_id"], status="in_progress")
    _move(client, agent["headers"], task["id"], "review")
    r = client.patch(
        f"{API}/tasks/{task['id']}",
        headers=agent["headers"],
        json={"assignee_id": me, "title": "Summarise the trackers"},
    )
    assert r.status_code == 200, r.text

    listed = client.get(
        f"{API}/tasks/", headers=owner, params={"assignee_id": me, "status": "review"}
    ).json()["data"]
    assert [each["handover"]["bot_user"]["id"] for each in listed] == [agent["id"]]


def test_a_deleted_bot_users_hand_over_still_names_it(
    client: TestClient, owner: Headers, agent: dict[str, Any]
) -> None:
    task = _create(client, owner, project_id=agent["project_id"], status="in_progress")
    _move(client, agent["headers"], task["id"], "review")
    r = client.delete(f"{API}/bot-users/{agent['id']}", headers=owner)
    assert r.status_code == 200, r.text

    bot_user = _shown(client, owner, task["id"])["handover"]["bot_user"]
    assert (bot_user["name"], bot_user["deleted"]) == ("research-agent", True)
