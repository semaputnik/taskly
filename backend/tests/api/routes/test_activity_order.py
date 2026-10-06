"""
Reading the log oldest first.

The log reads newest first (FR-10.10), and can be turned to oldest first. The
order changes which end of the log a page starts from and nothing about what
the log holds, so it has to combine with every narrowing and with paging
without dropping or repeating an entry.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
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


def _five_tasks(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    for n in range(5):
        create_task(client, owner, project_id=project_id, title=f"T{n}")


def test_the_log_reads_newest_first_unless_asked_otherwise(
    client: TestClient, owner: Headers
) -> None:
    _five_tasks(client, owner)

    assert _titles(_log(client, owner))[:5] == ["T4", "T3", "T2", "T1", "T0"]
    assert _titles(_log(client, owner, order="newest"))[:5] == [
        "T4",
        "T3",
        "T2",
        "T1",
        "T0",
    ]


def test_oldest_turns_the_log_around(client: TestClient, owner: Headers) -> None:
    _five_tasks(client, owner)

    newest = _log(client, owner, order="newest")
    oldest = _log(client, owner, order="oldest")

    assert oldest["count"] == newest["count"]
    assert [e["id"] for e in oldest["data"]] == [
        e["id"] for e in reversed(newest["data"])
    ]
    # The project's own creation is the first thing that happened.
    assert oldest["data"][0]["action"] == "project_created"


def test_oldest_pages_walk_the_whole_log_once(
    client: TestClient, owner: Headers
) -> None:
    _five_tasks(client, owner)
    everything = _log(client, owner, order="oldest")

    seen: list[str] = []
    for skip in (0, 2, 4):
        page = _log(client, owner, order="oldest", skip=skip, limit=2)
        seen += [e["id"] for e in page["data"]]

    assert seen == [e["id"] for e in everything["data"]]


def test_the_order_combines_with_the_kind_and_the_actor(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot = token_headers(client, owner, bot_user["id"])
    create_task(client, owner, project_id=project_id, title="Mine")
    create_task(client, bot, project_id=project_id, title="First by bot")
    create_task(client, bot, project_id=project_id, title="Second by bot")

    by_bot = _log(
        client,
        owner,
        order="oldest",
        actor_bot_user_id=bot_user["id"],
        kind="created",
    )

    assert _titles(by_bot) == ["First by bot", "Second by bot"]
    assert by_bot["count"] == 2


def test_an_unknown_order_is_refused(client: TestClient, owner: Headers) -> None:
    r = client.get(f"{API}/activity-log/", headers=owner, params={"order": "sideways"})
    assert r.status_code == 422
