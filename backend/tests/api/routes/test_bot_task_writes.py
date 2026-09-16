"""
What a bot user can change in tasks, driven the way an integration would:
over HTTP with its own token.

Mostly matrix-shaped — action × task or subtask × in or out of scope ×
permission granted or not — so a new case is a row rather than a function.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
    error_code,
    issue_bot_headers,
    token_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]

PERMISSION = {
    "create": "create_tasks",
    "read": "read_tasks",
    "update": "update_tasks",
    "delete": "delete_tasks",
}


def _inbox(client: TestClient, headers: Headers) -> str:
    projects = client.get(f"{API}/projects/", headers=headers).json()["data"]
    inbox_id: str = next(p["id"] for p in projects if p["is_inbox"])
    return inbox_id


def _title(client: TestClient, headers: Headers, task_id: str) -> str | None:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    return r.json()["title"] if r.status_code == 200 else None


def _task_count(client: TestClient, headers: Headers) -> int:
    count: int = client.get(f"{API}/tasks/", headers=headers).json()["count"]
    return count


# --- The matrix ---------------------------------------------------------------


def _act(
    client: TestClient, bot: Headers, action: str, target: str, *, subtask: bool
) -> Response:
    """
    Do `action` through the bot, aimed at `target`: for create, the task a
    subtask goes under, or the project a task goes into; for everything else,
    the task itself.
    """
    if action == "create":
        body = {"title": "By the bot"}
        body["parent_id" if subtask else "project_id"] = target
        return client.post(f"{API}/tasks/", headers=bot, json=body)
    if action == "read":
        return client.get(f"{API}/tasks/{target}", headers=bot)
    if action == "update":
        return client.patch(
            f"{API}/tasks/{target}", headers=bot, json={"title": "Changed"}
        )
    # The cascade is confirmed as a human has to confirm it.
    return client.delete(
        f"{API}/tasks/{target}", headers=bot, params={"delete_subtasks": True}
    )


@pytest.mark.parametrize("granted", [True, False], ids=["granted", "not granted"])
@pytest.mark.parametrize("in_scope", [True, False], ids=["in scope", "out of scope"])
@pytest.mark.parametrize("subtask", [False, True], ids=["task", "subtask"])
@pytest.mark.parametrize("action", ["create", "read", "update", "delete"])
def test_each_action_needs_its_permission_and_the_scope(
    client: TestClient,
    db: Session,
    action: str,
    subtask: bool,
    in_scope: bool,
    granted: bool,
) -> None:
    owner = create_user_headers(client, db)
    scoped = create_project(client, owner, "Scoped")
    unscoped = create_project(client, owner, "Unscoped")
    project_id = scoped if in_scope else unscoped
    root = create_task(client, owner, project_id=project_id, title="Root")
    child = create_task(client, owner, parent_id=root, title="Child")
    # Granted alone, or everything except it: each permission stands on its
    # own, whatever else the bot holds.
    permission = PERMISSION[action]
    permissions = (
        {permission: True} if granted else {**ALL_PERMISSIONS, permission: False}
    )
    bot = issue_bot_headers(
        client, owner, project_ids=[scoped], permissions=permissions
    )
    before = _task_count(client, owner)

    if action == "create":
        target = root if subtask else project_id
    else:
        target = child if subtask else root
    r = _act(client, bot, action, target, subtask=subtask)

    if not in_scope:
        assert r.status_code == 403, r.text
        assert error_code(r) == "outside_scope"
    elif not granted:
        assert r.status_code == 403, r.text
        assert error_code(r) == "permission_not_granted"
    else:
        assert r.status_code == 200, r.text
        if action == "create":
            assert _task_count(client, owner) == before + 1
            assert r.json()["project_id"] == project_id
            assert r.json()["parent_id"] == (root if subtask else None)
        elif action == "update":
            assert _title(client, owner, target) == "Changed"
        elif action == "delete":
            assert _title(client, owner, target) is None
        return

    # A refusal leaves everything as it was.
    assert _task_count(client, owner) == before
    assert _title(client, owner, root) == "Root"
    assert _title(client, owner, child) == "Child"


# --- Creating without a project -----------------------------------------------


@pytest.mark.parametrize("inbox_in_scope", [True, False], ids=["in scope", "not"])
def test_a_task_without_a_project_goes_to_the_inbox_only_if_it_is_in_scope(
    client: TestClient, db: Session, inbox_in_scope: bool
) -> None:
    owner = create_user_headers(client, db)
    inbox = _inbox(client, owner)
    other = create_project(client, owner)
    bot = issue_bot_headers(
        client,
        owner,
        project_ids=[inbox, other] if inbox_in_scope else [other],
        permissions=ALL_PERMISSIONS,
    )

    r = client.post(f"{API}/tasks/", headers=bot, json={"title": "Unsorted"})

    if inbox_in_scope:
        assert r.status_code == 200, r.text
        assert r.json()["project_id"] == inbox
    else:
        # Refused rather than written somewhere the bot cannot see.
        assert r.status_code == 403
        assert error_code(r) == "outside_scope"
        assert _task_count(client, owner) == 0


# --- Moving -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source_in_scope", "destination_in_scope"),
    [(True, True), (True, False), (False, True)],
    ids=["both in scope", "only the source", "only the destination"],
)
def test_moving_a_task_needs_both_ends_in_scope(
    client: TestClient,
    db: Session,
    source_in_scope: bool,
    destination_in_scope: bool,
) -> None:
    owner = create_user_headers(client, db)
    source = create_project(client, owner, "Source")
    destination = create_project(client, owner, "Destination")
    task_id = create_task(client, owner, project_id=source)
    scope = [
        project_id
        for project_id, included in (
            (source, source_in_scope),
            (destination, destination_in_scope),
        )
        if included
    ]
    bot = issue_bot_headers(
        client, owner, project_ids=scope, permissions=ALL_PERMISSIONS
    )

    r = client.patch(
        f"{API}/tasks/{task_id}", headers=bot, json={"project_id": destination}
    )

    where = client.get(f"{API}/tasks/{task_id}", headers=owner).json()["project_id"]
    if source_in_scope and destination_in_scope:
        assert r.status_code == 200, r.text
        assert where == destination
    else:
        assert r.status_code == 403
        assert error_code(r) == "outside_scope"
        assert where == source


# --- Archived projects --------------------------------------------------------


def test_an_archived_project_refuses_every_write_whatever_the_bot_holds(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    archived = create_project(client, owner)
    root = create_task(client, owner, project_id=archived, title="Root")
    child = create_task(client, owner, parent_id=root, title="Child")
    bot = issue_bot_headers(
        client, owner, project_ids=[archived], permissions=ALL_PERMISSIONS
    )
    assert (
        client.post(f"{API}/projects/{archived}/archive", headers=owner).status_code
        == 200
    )

    requests: list[Callable[[], Response]] = [
        lambda: client.post(
            f"{API}/tasks/", headers=bot, json={"title": "New", "project_id": archived}
        ),
        lambda: client.post(
            f"{API}/tasks/", headers=bot, json={"title": "New", "parent_id": root}
        ),
        lambda: client.patch(
            f"{API}/tasks/{child}", headers=bot, json={"title": "Changed"}
        ),
        lambda: client.patch(
            f"{API}/tasks/{root}",
            headers=bot,
            json={"completed": True, "subtasks": "complete"},
        ),
        lambda: client.delete(
            f"{API}/tasks/{root}", headers=bot, params={"delete_subtasks": True}
        ),
    ]
    for request in requests:
        r = request()
        assert r.status_code == 403, r.text
        assert error_code(r) == "project_archived"

    assert _title(client, owner, root) == "Root"
    assert _title(client, owner, child) == "Child"
    assert (
        client.get(f"{API}/tasks/", headers=owner, params={"archived": True}).json()[
            "count"
        ]
        == 2
    )


# --- Projects are never a bot's to change -------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/projects/", {"name": "Bot's own"}),
        ("patch", "/projects/{project_id}", {"name": "Renamed"}),
        ("post", "/projects/{project_id}/archive", None),
        ("post", "/projects/{project_id}/unarchive", None),
        ("delete", "/projects/{project_id}", None),
    ],
    ids=["create", "update", "archive", "unarchive", "delete"],
)
def test_no_project_write_is_open_to_a_bot_with_every_permission(
    client: TestClient,
    db: Session,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Mine")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    r = client.request(
        method,
        f"{API}{path.format(project_id=project_id)}",
        headers=bot,
        json=body,
    )
    assert r.status_code == 403, r.text
    assert error_code(r) == "human_only"

    projects = client.get(f"{API}/projects/", headers=owner).json()["data"]
    assert sorted(p["name"] for p in projects) == ["Inbox", "Mine"]


# --- Attribution --------------------------------------------------------------


def test_every_change_a_bot_makes_is_logged_as_the_bots(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot_user = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Release bot",
    )
    bot = token_headers(client, owner, bot_user["id"])

    task_id = client.post(
        f"{API}/tasks/", headers=bot, json={"title": "Ship", "project_id": project_id}
    ).json()["id"]
    r = client.patch(f"{API}/tasks/{task_id}", headers=bot, json={"completed": True})
    assert r.status_code == 200, r.text
    r = client.delete(f"{API}/tasks/{task_id}", headers=bot)
    assert r.status_code == 200, r.text

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    by_bot = [e for e in entries if e["entity_id"] == task_id]
    assert [e["action"] for e in by_bot] == [
        "task_deleted",
        "task_completed",
        "task_created",
    ]
    for entry in by_bot:
        assert entry["actor_bot_user_id"] == bot_user["id"]
        assert entry["actor_bot_user_name"] == "Release bot"
        # Never the owner's doing.
        assert entry["actor_id"] is None


def test_the_owners_own_changes_still_name_the_owner(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    me = client.get(f"{API}/users/me", headers=owner).json()["id"]
    project_id = create_project(client, owner)
    issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    create_task(client, owner, project_id=project_id, title="Mine")

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    assert entries
    for entry in entries:
        assert entry["actor_id"] == me
        assert entry["actor_bot_user_id"] is None
        assert entry["actor_bot_user_name"] is None


def test_a_refused_bot_request_logs_nothing(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    before = client.get(f"{API}/activity-log/", headers=owner).json()["count"]
    bot = issue_bot_headers(client, owner, project_ids=[project_id], permissions={})

    client.patch(f"{API}/tasks/{task_id}", headers=bot, json={"title": "Nope"})
    client.delete(f"{API}/tasks/{task_id}", headers=bot)

    assert client.get(f"{API}/activity-log/", headers=owner).json()["count"] == before
