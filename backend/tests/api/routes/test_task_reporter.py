"""
Who filed a task.

Every task has an author, and it is never the request's to choose: it is
whoever made the request. This is the read-only half of the promise that a
bot user's action is always attributable and never passed off as its owner's.
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


def _task(client: TestClient, headers: Headers, task_id: str) -> Any:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _me(client: TestClient, headers: Headers) -> str:
    r = client.get(f"{API}/users/me", headers=headers)
    assert r.status_code == 200, r.text
    user_id: str = r.json()["id"]
    return user_id


def _bot(
    client: TestClient, owner: Headers, project_id: str, name: str = "Filing agent"
) -> tuple[dict[str, Any], Headers]:
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS, name=name
    )
    return bot_user, token_headers(client, owner, bot_user["id"])


# --- Who a new task names ------------------------------------------------------


def test_a_task_the_user_files_names_the_user(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)

    task = _task(client, owner, task_id)

    assert task["reporter_id"] == _me(client, owner)
    assert task["reporter_bot_user"] is None


def test_a_task_a_bot_user_files_names_the_bot_user(
    client: TestClient, owner: Headers
) -> None:
    """A bot user's work is its own, never recorded as its owner's."""
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)

    task_id = create_task(client, bot, project_id=project_id, title="Filed by a bot")
    task = _task(client, owner, task_id)

    assert task["reporter_id"] == bot_user["id"]
    assert task["reporter_bot_user"] == {
        "id": bot_user["id"],
        "name": "Filing agent",
        "deleted": False,
    }


def test_a_subtask_names_whoever_filed_it(client: TestClient, owner: Headers) -> None:
    """A subtask is a full task, and holds its own author like any other."""
    project_id = create_project(client, owner)
    root = create_task(client, owner, project_id=project_id)
    bot_user, bot = _bot(client, owner, project_id)

    child = create_task(client, bot, parent_id=root, title="Bot's subtask")

    assert _task(client, owner, root)["reporter_id"] == _me(client, owner)
    assert _task(client, owner, child)["reporter_id"] == bot_user["id"]


def test_a_deleted_bot_user_is_still_named_on_what_it_filed(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)
    task_id = create_task(client, bot, project_id=project_id)

    r = client.delete(f"{API}/bot-users/{bot_user['id']}", headers=owner)
    assert r.status_code == 200, r.text

    task = _task(client, owner, task_id)
    assert task["reporter_id"] == bot_user["id"]
    assert task["reporter_bot_user"]["deleted"] is True
    assert task["reporter_bot_user"]["name"] == "Filing agent"


# --- The reporter is a fact, not a field ---------------------------------------


def test_creating_a_task_cannot_choose_its_reporter(
    client: TestClient, owner: Headers
) -> None:
    """
    A request that names someone else as the author is not honoured. The
    reporter comes from who is making the request, and nothing else.
    """
    project_id = create_project(client, owner)
    bot_user, _ = _bot(client, owner, project_id)

    r = client.post(
        f"{API}/tasks/",
        headers=owner,
        json={
            "title": "Not yours to claim",
            "project_id": project_id,
            "reporter_id": bot_user["id"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["reporter_id"] == _me(client, owner)


def test_updating_a_task_cannot_change_its_reporter(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user, _ = _bot(client, owner, project_id)
    task_id = create_task(client, owner, project_id=project_id)

    r = client.patch(
        f"{API}/tasks/{task_id}",
        headers=owner,
        json={"reporter_id": bot_user["id"], "title": "Renamed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Renamed"
    assert r.json()["reporter_id"] == _me(client, owner)


def test_a_bot_user_cannot_file_a_task_as_its_owner(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    _, bot = _bot(client, owner, project_id)

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "Passing itself off",
            "project_id": project_id,
            "reporter_id": _me(client, owner),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["reporter_bot_user"] is not None


# --- What carries the reporter along -------------------------------------------


def test_the_next_occurrence_keeps_the_reporter_of_the_one_before(
    client: TestClient, owner: Headers
) -> None:
    """
    The series was filed once. Each occurrence is that same work recurring,
    not something new that whoever completed the last one has filed.
    """
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "Weekly sweep",
            "project_id": project_id,
            "due_date": "2026-10-01",
            "recurrence": {"frequency": "weekly"},
        },
    )
    assert r.status_code == 200, r.text
    first = r.json()["id"]

    # The owner completes it, which spawns the next occurrence.
    r = client.patch(f"{API}/tasks/{first}", headers=owner, json={"status": "done"})
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/tasks/", headers=owner, params={"project_id": project_id})
    assert r.status_code == 200, r.text
    successors = [t for t in r.json()["data"] if t["id"] != first]
    assert len(successors) == 1
    assert successors[0]["reporter_id"] == bot_user["id"], (
        "the occurrence carries the reporter of the one before it, not the "
        "actor who completed that one"
    )


def test_a_restored_task_keeps_the_reporter_it_had(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)
    task_id = create_task(client, bot, project_id=project_id)

    r = client.delete(f"{API}/tasks/{task_id}", headers=owner)
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/activity-log/", headers=owner, params={"kind": "deleted"})
    entry = r.json()["data"][0]
    r = client.post(f"{API}/activity-log/{entry['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    assert _task(client, owner, task_id)["reporter_id"] == bot_user["id"]


def test_a_task_in_a_list_names_its_reporter(
    client: TestClient, owner: Headers
) -> None:
    """The list serialises tasks through the same read model the panel uses."""
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)
    create_task(client, owner, project_id=project_id, title="Mine")
    create_task(client, bot, project_id=project_id, title="Theirs")

    r = client.get(f"{API}/tasks/", headers=owner, params={"project_id": project_id})
    assert r.status_code == 200, r.text
    by_title = {t["title"]: t for t in r.json()["data"]}

    assert by_title["Mine"]["reporter_id"] == _me(client, owner)
    assert by_title["Theirs"]["reporter_id"] == bot_user["id"]
    assert by_title["Theirs"]["reporter_bot_user"]["name"] == "Filing agent"


# --- Narrowing the list to one actor's own filings ------------------------------


def test_filter_by_reporter_keeps_only_what_that_actor_filed(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)
    create_task(client, owner, project_id=project_id, title="Mine")
    create_task(client, bot, project_id=project_id, title="Theirs")

    def titles(reporter_id: str) -> list[str]:
        r = client.get(
            f"{API}/tasks/", headers=owner, params={"reporter_id": reporter_id}
        )
        assert r.status_code == 200, r.text
        return [t["title"] for t in r.json()["data"]]

    assert titles(_me(client, owner)) == ["Mine"]
    assert titles(bot_user["id"]) == ["Theirs"]


def test_the_reporter_filter_narrows_alongside_the_others(
    client: TestClient, owner: Headers
) -> None:
    """Filters combine with AND: adding one always narrows (FR-06.3)."""
    project_id = create_project(client, owner)
    _, bot = _bot(client, owner, project_id)
    elsewhere = create_project(client, owner, "Elsewhere")
    create_task(client, bot, project_id=project_id, title="Bot here")
    create_task(client, owner, project_id=project_id, title="Mine here")
    create_task(client, owner, project_id=elsewhere, title="Mine elsewhere")

    me = _me(client, owner)
    r = client.get(
        f"{API}/tasks/",
        headers=owner,
        params={"reporter_id": me, "project_id": project_id},
    )
    assert r.status_code == 200, r.text
    assert [t["title"] for t in r.json()["data"]] == ["Mine here"]


def test_the_reporter_filter_counts_what_it_narrowed_to(
    client: TestClient, owner: Headers
) -> None:
    """Paging a narrowed list must page the narrowing, not the whole list."""
    project_id = create_project(client, owner)
    bot_user, bot = _bot(client, owner, project_id)
    for n in range(3):
        create_task(client, bot, project_id=project_id, title=f"Bot {n}")
    create_task(client, owner, project_id=project_id, title="Mine")

    r = client.get(
        f"{API}/tasks/",
        headers=owner,
        params={"reporter_id": bot_user["id"], "limit": 2},
    )
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 3
    assert len(r.json()["data"]) == 2


def test_a_reporter_filter_reaches_nothing_outside_the_callers_own_tasks(
    client: TestClient, db: Session, owner: Headers
) -> None:
    """The filter narrows; it never widens past whose tasks these are."""
    stranger = create_user_headers(client, db)
    stranger_project = create_project(client, stranger, "Theirs")
    create_task(client, stranger, project_id=stranger_project, title="Not yours")

    r = client.get(
        f"{API}/tasks/", headers=owner, params={"reporter_id": _me(client, stranger)}
    )
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0
