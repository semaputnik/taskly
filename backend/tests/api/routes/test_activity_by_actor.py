"""
Reading one bot user's activity: the log narrowed to a single actor.

An operator's question is "what has this integration been doing", and the log
already knows — every entry records the bot user that made the change
(FR-10.2). What was missing was a way to ask. The narrowing never widens the
log: it is the caller's own entries, filtered (FR-10.7).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
    token_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _log(client: TestClient, headers: Headers, **params: Any) -> Any:
    r = client.get(f"{API}/activity-log/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _titles(page: Any) -> list[str]:
    return [entry["details"].get("title") for entry in page["data"]]


def _bot_with_work(
    client: TestClient, owner: Headers, name: str = "Triage bot"
) -> tuple[str, Headers, str]:
    """A bot user with a token, a project in scope, and a task it created."""
    project_id = create_project(client, owner, name)
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS, name=name
    )
    bot = token_headers(client, owner, bot_user["id"])
    create_task(client, bot, project_id=project_id, title=f"{name} did this")
    return bot_user["id"], bot, project_id


# --- What the filter narrows to ------------------------------------------------


def test_the_filter_returns_only_that_bot_users_entries(
    client: TestClient, owner: Headers
) -> None:
    bot_id, bot, project_id = _bot_with_work(client, owner)
    another_id, another, _ = _bot_with_work(client, owner, name="Nightly sync")
    create_task(client, owner, project_id=project_id, title="Mine")

    page = _log(client, owner, actor_bot_user_id=bot_id)
    assert _titles(page) == ["Triage bot did this"]
    assert page["count"] == 1
    for entry in page["data"]:
        assert entry["actor_bot_user_id"] == bot_id
        assert entry["actor_bot_user_name"] == "Triage bot"
        assert entry["actor_id"] is None

    # The other bot user's work, and the owner's own, are somebody else's feed.
    assert _titles(_log(client, owner, actor_bot_user_id=another_id)) == [
        "Nightly sync did this"
    ]
    assert "Mine" in _titles(_log(client, owner))


def test_the_narrowed_feed_is_the_same_entries_as_the_whole_log(
    client: TestClient, owner: Headers
) -> None:
    bot_id, bot, project_id = _bot_with_work(client, owner)
    task_id = create_task(client, bot, project_id=project_id, title="Second")
    assert (
        client.patch(
            f"{API}/tasks/{task_id}", headers=bot, json={"status": "done"}
        ).status_code
        == 200
    )

    narrowed = _log(client, owner, actor_bot_user_id=bot_id)["data"]
    whole = [
        entry
        for entry in _log(client, owner)["data"]
        if entry["actor_bot_user_id"] == bot_id
    ]
    assert narrowed == whole
    # Newest first, as the log always is.
    assert [entry["action"] for entry in narrowed][0] == "task_completed"


def test_the_filter_pages_without_losing_its_order(
    client: TestClient, owner: Headers
) -> None:
    bot_id, bot, project_id = _bot_with_work(client, owner)
    for index in range(4):
        create_task(client, bot, project_id=project_id, title=f"Task {index}")

    page = _log(client, owner, actor_bot_user_id=bot_id, limit=2)
    assert page["count"] == 5
    assert _titles(page) == ["Task 3", "Task 2"]
    later = _log(client, owner, actor_bot_user_id=bot_id, skip=2, limit=2)
    assert _titles(later) == ["Task 1", "Task 0"]


# --- What it never reaches -----------------------------------------------------


def test_another_users_bot_is_an_empty_feed_not_a_leak(
    client: TestClient, db: Session, owner: Headers
) -> None:
    bot_id, _, _ = _bot_with_work(client, owner)

    other = create_user_headers(client, db)
    create_task(client, other, title="Theirs")

    page = _log(client, other, actor_bot_user_id=bot_id)
    assert page == {"data": [], "count": 0}
    # And a bot user that exists nowhere reads exactly the same.
    unknown = _log(
        client, other, actor_bot_user_id="00000000-0000-0000-0000-000000000000"
    )
    assert unknown == page


def test_the_superuser_gains_no_reach_through_the_filter(
    client: TestClient,
    owner: Headers,
    superuser_token_headers: dict[str, str],
) -> None:
    bot_id, _, _ = _bot_with_work(client, owner)

    page = _log(client, superuser_token_headers, actor_bot_user_id=bot_id)
    assert page == {"data": [], "count": 0}


def test_a_bot_user_cannot_read_any_log_at_all(
    client: TestClient, owner: Headers
) -> None:
    bot_id, bot, _ = _bot_with_work(client, owner)

    r = client.get(
        f"{API}/activity-log/", headers=bot, params={"actor_bot_user_id": bot_id}
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "human_only"


# --- After the bot user is gone ------------------------------------------------


def test_a_deleted_bot_users_feed_is_still_readable(
    client: TestClient, owner: Headers
) -> None:
    """What it did keeps naming it (FR-08.19)."""
    bot_id, _, _ = _bot_with_work(client, owner)
    assert client.delete(f"{API}/bot-users/{bot_id}", headers=owner).status_code == 200

    page = _log(client, owner, actor_bot_user_id=bot_id)
    assert _titles(page) == ["Triage bot did this"]
    assert page["data"][0]["actor_bot_user_name"] == "Triage bot"
