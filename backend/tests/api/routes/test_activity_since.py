"""
Counting what the bot users did since a moment: the day page's sentence.

The dashboard says how many changes the user's agents made since their last
visit (FR-06.12). The log already records who made each change (FR-10.2) and
when; the two narrowings here let the page ask for exactly that count rather
than reading pages of entries to count them itself. Neither ever widens the log
past the reader's own entries (FR-10.7).
"""

from datetime import UTC, datetime, timedelta, timezone
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


def _bot(client: TestClient, owner: Headers, name: str) -> tuple[Headers, str]:
    project_id = create_project(client, owner, name)
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS, name=name
    )
    return token_headers(client, owner, bot_user["id"]), project_id


def test_by_bots_keeps_every_bot_users_changes_and_none_of_the_owners(
    client: TestClient, owner: Headers
) -> None:
    triage, triage_project = _bot(client, owner, "Triage bot")
    sync, sync_project = _bot(client, owner, "Nightly sync")
    create_task(client, triage, project_id=triage_project, title="Triaged")
    create_task(client, owner, project_id=triage_project, title="Mine")
    create_task(client, sync, project_id=sync_project, title="Synced")

    page = _log(client, owner, by_bots=True)
    assert _titles(page) == ["Synced", "Triaged"]
    assert page["count"] == 2
    assert all(entry["actor_bot_user_id"] for entry in page["data"])
    # Unset, the log is whole.
    assert "Mine" in _titles(_log(client, owner))


def test_since_keeps_only_what_came_after_the_moment(
    client: TestClient, owner: Headers
) -> None:
    create_task(client, owner, title="Before")
    entries = _log(client, owner)["data"]
    moment = entries[0]["created_at"]
    create_task(client, owner, title="After")

    page = _log(client, owner, since=moment)
    assert _titles(page) == ["After"]
    assert page["count"] == 1


def test_since_reads_a_moment_in_any_offset(client: TestClient, owner: Headers) -> None:
    create_task(client, owner, title="Recent")
    hour_ago = datetime.now(timezone(timedelta(hours=5))) - timedelta(hours=1)
    in_an_hour = datetime.now(UTC) + timedelta(hours=1)

    assert _titles(_log(client, owner, since=hour_ago.isoformat())) == ["Recent"]
    assert _log(client, owner, since=in_an_hour.isoformat())["count"] == 0


def test_the_two_combine_into_the_day_pages_count(
    client: TestClient, owner: Headers
) -> None:
    bot, project_id = _bot(client, owner, "Triage bot")
    create_task(client, bot, project_id=project_id, title="Old news")
    moment = _log(client, owner)["data"][0]["created_at"]
    create_task(client, bot, project_id=project_id, title="News")
    create_task(client, owner, project_id=project_id, title="Mine")

    page = _log(client, owner, by_bots=True, since=moment, limit=1)
    assert page["count"] == 1
    assert _titles(page) == ["News"]


def test_neither_narrowing_reaches_another_users_log(
    client: TestClient, db: Session, owner: Headers
) -> None:
    bot, project_id = _bot(client, owner, "Triage bot")
    create_task(client, bot, project_id=project_id, title="Theirs")

    other = create_user_headers(client, db)
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    assert _log(client, other, by_bots=True, since=hour_ago.isoformat()) == {
        "data": [],
        "count": 0,
    }
