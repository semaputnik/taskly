import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import BotUser
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


def _me(client: TestClient, headers: Headers) -> str:
    user_id: str = client.get(f"{API}/users/me", headers=headers).json()["id"]
    return user_id


def _bot(client: TestClient, headers: Headers, name: str = "Triage bot") -> str:
    bot_id: str = create_bot_user(
        client, headers, project_ids=[], permissions={}, name=name
    )["id"]
    return bot_id


def _delete_bot(db: Session, bot_id: str) -> None:
    # Marked deleted directly: the endpoint that deletes a bot user comes with
    # semaputnik/taskly#49, and all that matters here is the state it leaves.
    bot = db.get(BotUser, uuid.UUID(bot_id))
    assert bot is not None
    db.refresh(bot)
    bot.deleted_at = datetime.now(UTC)
    db.add(bot)
    db.commit()


def _assign(
    client: TestClient, headers: Headers, how: str, assignee_id: str | None
) -> tuple[int, dict[str, Any]]:
    """Assign a new task, on creation or by an update, and return the result."""
    if how == "create":
        r = client.post(
            f"{API}/tasks/",
            headers=headers,
            json={"title": "Assigned", "assignee_id": assignee_id},
        )
    else:
        task_id = create_task(client, headers, title="Assigned")
        r = client.patch(
            f"{API}/tasks/{task_id}", headers=headers, json={"assignee_id": assignee_id}
        )
    return r.status_code, r.json()


# --- Who a task can be assigned to --------------------------------------------


@pytest.mark.parametrize("how", ["create", "update"])
def test_a_task_can_be_assigned_to_one_of_the_owners_bot_users(
    client: TestClient, db: Session, how: str
) -> None:
    owner = create_user_headers(client, db)
    bot_id = _bot(client, owner)

    status, task = _assign(client, owner, how, bot_id)
    assert status == 200, task
    assert task["assignee_id"] == bot_id
    assert task["assignee_bot_user"] == {
        "id": bot_id,
        "name": "Triage bot",
        "deleted": False,
    }

    r = client.get(f"{API}/tasks/{task['id']}", headers=owner)
    assert r.json()["assignee_bot_user"]["id"] == bot_id


@pytest.mark.parametrize("how", ["create", "update"])
def test_a_task_assigned_to_the_owner_names_no_bot_user(
    client: TestClient, db: Session, how: str
) -> None:
    owner = create_user_headers(client, db)
    me = _me(client, owner)

    status, task = _assign(client, owner, how, me)
    assert status == 200, task
    assert task["assignee_id"] == me
    assert task["assignee_bot_user"] is None


def test_reassigning_moves_between_the_owner_and_a_bot_user(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    me = _me(client, owner)
    bot_id = _bot(client, owner)
    task_id = create_task(client, owner)

    for assignee_id in (me, bot_id, me, None):
        r = client.patch(
            f"{API}/tasks/{task_id}", headers=owner, json={"assignee_id": assignee_id}
        )
        assert r.status_code == 200, r.text
        assert r.json()["assignee_id"] == assignee_id
        assert (r.json()["assignee_bot_user"] is not None) == (assignee_id == bot_id)


@pytest.mark.parametrize("how", ["create", "update"])
@pytest.mark.parametrize(
    "whom", ["another user", "another user's bot user", "nobody known", "deleted bot"]
)
def test_assigning_outside_the_owner_and_their_live_bot_users_is_refused(
    client: TestClient, db: Session, how: str, whom: str
) -> None:
    owner = create_user_headers(client, db)
    other = create_user_headers(client, db)
    if whom == "another user":
        assignee_id = _me(client, other)
    elif whom == "another user's bot user":
        assignee_id = _bot(client, other)
    elif whom == "nobody known":
        assignee_id = str(uuid.uuid4())
    else:
        assignee_id = _bot(client, owner)
        _delete_bot(db, assignee_id)

    status, body = _assign(client, owner, how, assignee_id)
    assert status == 400, body

    tasks = client.get(f"{API}/tasks/", headers=owner).json()["data"]
    assert all(t["assignee_id"] is None for t in tasks)


def test_a_bot_can_assign_a_task_in_its_scope_to_itself(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot_headers = token_headers(client, owner, bot["id"])
    task_id = create_task(client, owner, project_id=project_id)

    r = client.patch(
        f"{API}/tasks/{task_id}", headers=bot_headers, json={"assignee_id": bot["id"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_bot_user"]["id"] == bot["id"]


# --- Filtering ----------------------------------------------------------------


def test_the_assignee_filter_covers_bot_users(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    me = _me(client, owner)
    first_bot = _bot(client, owner, "First")
    second_bot = _bot(client, owner, "Second")
    tasks = {}
    for key, assignee_id in (
        ("me", me),
        ("first", first_bot),
        ("second", second_bot),
        ("nobody", None),
    ):
        tasks[key] = client.post(
            f"{API}/tasks/",
            headers=owner,
            json={"title": key, "assignee_id": assignee_id},
        ).json()["id"]

    def listed(**params: Any) -> set[str]:
        r = client.get(f"{API}/tasks/", headers=owner, params=params)
        assert r.status_code == 200, r.text
        return {t["id"] for t in r.json()["data"]}

    assert listed(assignee_id=first_bot) == {tasks["first"]}
    assert listed(assignee_id=me) == {tasks["me"]}
    # Nobody means nobody: a bot user on a task is somebody.
    assert listed(unassigned=True) == {tasks["nobody"]}


# --- Deleted bot users --------------------------------------------------------


def test_a_deleted_bot_user_stays_on_its_tasks_and_takes_no_new_ones(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot_id = _bot(client, owner, "Retired bot")
    token = token_headers(client, owner, bot_id)
    task_id = client.post(
        f"{API}/tasks/", headers=owner, json={"title": "Kept", "assignee_id": bot_id}
    ).json()["id"]

    _delete_bot(db, bot_id)

    r = client.get(f"{API}/tasks/{task_id}", headers=owner)
    assert r.json()["assignee_id"] == bot_id
    assert r.json()["assignee_bot_user"] == {
        "id": bot_id,
        "name": "Retired bot",
        "deleted": True,
    }
    # Its tasks are still found by it.
    r = client.get(f"{API}/tasks/", headers=owner, params={"assignee_id": bot_id})
    assert [t["id"] for t in r.json()["data"]] == [task_id]

    # Saving the task as it is — the form sends the assignee back — is not a
    # new assignment.
    r = client.patch(
        f"{API}/tasks/{task_id}",
        headers=owner,
        json={"title": "Kept, renamed", "assignee_id": bot_id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] == bot_id

    r = client.post(
        f"{API}/tasks/", headers=owner, json={"title": "New", "assignee_id": bot_id}
    )
    assert r.status_code == 400

    assert bot_id not in client.get(f"{API}/bot-users/", headers=owner).text
    assert client.get(f"{API}/tasks/", headers=token).status_code == 401


def test_a_recurring_task_passes_its_bot_assignee_to_the_next_occurrence(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot_id = _bot(client, owner)
    task_id = client.post(
        f"{API}/tasks/",
        headers=owner,
        json={
            "title": "Weekly report",
            "due_date": "2026-09-14",
            "recurrence": {"frequency": "weekly"},
            "assignee_id": bot_id,
        },
    ).json()["id"]

    r = client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"completed": True})
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/tasks/", headers=owner, params={"completed": False}).json()[
        "data"
    ]
    assert [(t["title"], t["assignee_id"]) for t in r] == [("Weekly report", bot_id)]


# --- The activity log ---------------------------------------------------------


def test_assignment_entries_name_a_bot_user_as_it_was_called_then(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot_id = _bot(client, owner, "Triage bot")
    task_id = create_task(client, owner, title="Sort the inbox")

    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"assignee_id": bot_id})
    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"assignee_id": None})

    # Renamed and then deleted: the entries still say who it was.
    bot = db.get(BotUser, uuid.UUID(bot_id))
    assert bot is not None
    db.refresh(bot)
    bot.name = "Something else"
    db.add(bot)
    db.commit()
    _delete_bot(db, bot_id)

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    unassigned, assigned = (
        e
        for e in entries
        if e["entity_id"] == task_id
        and e["action"] in {"task_assigned", "task_unassigned"}
    )
    named = {"type": "bot_user", "id": bot_id, "name": "Triage bot"}
    assert assigned["action"] == "task_assigned"
    assert assigned["details"]["assignee"] == named
    assert assigned["details"]["assignee_id"] == bot_id
    assert assigned["details"]["previous_assignee"] is None
    assert unassigned["action"] == "task_unassigned"
    assert unassigned["details"]["previous_assignee"] == named


def test_assignment_entries_name_the_owner_as_a_user(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    me = _me(client, owner)
    task_id = create_task(client, owner)

    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"assignee_id": me})

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    assigned = next(e for e in entries if e["action"] == "task_assigned")
    assert assigned["details"]["assignee_id"] == me
    assert assigned["details"]["assignee"] == {"type": "user", "id": me}
