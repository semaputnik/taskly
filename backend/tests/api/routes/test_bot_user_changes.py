"""
A bot user after it is created: renamed, rescoped, and deleted
(FR-08.18–FR-08.21).
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import BotUser
from tests.utils.bot import (
    ALL_PERMISSIONS,
    READ_ONLY,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
    error_code,
    token_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]

NO_PERMISSIONS = dict.fromkeys(ALL_PERMISSIONS, False)


def _update(client: TestClient, headers: Headers, bot_id: str, body: Any) -> Any:
    return client.patch(f"{API}/bot-users/{bot_id}", headers=headers, json=body)


def _scope(project_ids: list[str], permissions: dict[str, bool]) -> dict[str, Any]:
    return {"project_ids": project_ids, "permissions": permissions}


def _listed(client: TestClient, owner: Headers) -> list[dict[str, Any]]:
    bots: list[dict[str, Any]] = client.get(f"{API}/bot-users/", headers=owner).json()[
        "data"
    ]
    return bots


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


# --- Editing ------------------------------------------------------------------


def test_a_user_renames_a_bot_user_and_keeps_its_scope(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=READ_ONLY
    )

    r = _update(client, owner, bot["id"], {"name": "  Release notes agent "})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Release notes agent"
    assert r.json()["scope"] == bot["scope"]
    assert _listed(client, owner)[0]["name"] == "Release notes agent"


@pytest.mark.parametrize("name", ["", "   "])
def test_a_bot_user_cannot_be_renamed_to_nothing(
    client: TestClient, owner: Headers, name: str
) -> None:
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)

    assert _update(client, owner, bot["id"], {"name": name}).status_code == 422
    assert _listed(client, owner)[0]["name"] == bot["name"]


def test_a_new_scope_replaces_the_old_one_whole(
    client: TestClient, owner: Headers
) -> None:
    kept = create_project(client, owner, "Kept")
    dropped = create_project(client, owner, "Dropped")
    added = create_project(client, owner, "Added")
    bot = create_bot_user(
        client, owner, project_ids=[kept, dropped], permissions=ALL_PERMISSIONS
    )

    r = _update(
        client,
        owner,
        bot["id"],
        {"scope": _scope([kept, added, added], {"read_tasks": True})},
    )
    assert r.status_code == 200, r.text
    expected = {**NO_PERMISSIONS, "read_tasks": True}
    assert set(r.json()["scope"]["project_ids"]) == {kept, added}
    assert r.json()["scope"]["permissions"] == expected
    listed = _listed(client, owner)[0]
    assert set(listed["scope"]["project_ids"]) == {kept, added}
    assert listed["scope"]["permissions"] == expected
    assert r.json()["name"] == bot["name"]


def test_the_next_bot_request_is_authorized_against_the_new_scope(
    client: TestClient, owner: Headers
) -> None:
    kept = create_project(client, owner, "Kept")
    removed = create_project(client, owner, "Removed")
    removed_task = create_task(client, owner, project_id=removed)
    kept_task = create_task(client, owner, project_id=kept)
    bot = create_bot_user(
        client, owner, project_ids=[kept, removed], permissions=ALL_PERMISSIONS
    )
    bot_headers = token_headers(client, owner, bot["id"])
    assert (
        client.get(f"{API}/tasks/{removed_task}", headers=bot_headers).status_code
        == 200
    )

    r = _update(client, owner, bot["id"], {"scope": _scope([kept], READ_ONLY)})
    assert r.status_code == 200, r.text

    # The same token, no re-issue: the project that went is out of scope...
    r = client.get(f"{API}/tasks/{removed_task}", headers=bot_headers)
    assert r.status_code == 403
    assert error_code(r) == "outside_scope"
    listed = client.get(f"{API}/tasks/", headers=bot_headers).json()["data"]
    assert [t["id"] for t in listed] == [kept_task]
    # ...and a permission that went is no longer granted where it still reaches.
    r = client.patch(
        f"{API}/tasks/{kept_task}", headers=bot_headers, json={"title": "Changed"}
    )
    assert r.status_code == 403
    assert error_code(r) == "permission_not_granted"


def test_a_scope_widened_later_lets_the_bot_in_on_its_next_request(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    bot_headers = token_headers(client, owner, bot["id"])
    assert client.get(f"{API}/tasks/{task_id}", headers=bot_headers).status_code == 403

    _update(client, owner, bot["id"], {"scope": _scope([project_id], READ_ONLY)})

    assert client.get(f"{API}/tasks/{task_id}", headers=bot_headers).status_code == 200


def test_editing_leaves_the_token_as_it_was(client: TestClient, owner: Headers) -> None:
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    bot_headers = token_headers(client, owner, bot["id"])
    before = _listed(client, owner)[0]

    r = _update(
        client,
        owner,
        bot["id"],
        {"name": "Renamed", "scope": _scope([], ALL_PERMISSIONS)},
    )
    assert r.status_code == 200, r.text
    for field in ("has_token", "token_issued_at", "token_expires_at"):
        assert r.json()[field] == before[field]
    assert client.get(f"{API}/tasks/", headers=bot_headers).status_code == 200


def test_a_scope_can_only_list_the_owners_own_projects(
    client: TestClient, db: Session, owner: Headers
) -> None:
    mine = create_project(client, owner)
    others = create_project(client, create_user_headers(client, db))
    bot = create_bot_user(client, owner, project_ids=[mine], permissions=READ_ONLY)

    for project_id in (others, str(uuid.uuid4())):
        r = _update(
            client,
            owner,
            bot["id"],
            {"name": "Renamed", "scope": _scope([mine, project_id], ALL_PERMISSIONS)},
        )
        assert r.status_code == 404
    # Refused whole: neither the name nor the scope moved.
    assert _listed(client, owner)[0] == bot


def test_a_deleted_project_cannot_be_put_in_a_scope(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    client.delete(f"{API}/projects/{project_id}", headers=owner)

    r = _update(client, owner, bot["id"], {"scope": _scope([project_id], READ_ONLY)})
    assert r.status_code == 404


def test_a_deleted_project_drops_out_of_the_scope_until_it_is_restored(
    client: TestClient, owner: Headers
) -> None:
    kept = create_project(client, owner, "Kept")
    deleted = create_project(client, owner, "Deleted")
    task_id = create_task(client, owner, project_id=deleted)
    bot = create_bot_user(
        client, owner, project_ids=[kept, deleted], permissions=READ_ONLY
    )
    bot_headers = token_headers(client, owner, bot["id"])

    client.delete(f"{API}/projects/{deleted}", headers=owner)

    assert _listed(client, owner)[0]["scope"]["project_ids"] == [kept]
    assert client.get(f"{API}/tasks/{task_id}", headers=bot_headers).status_code == 404
    projects = client.get(f"{API}/projects/", headers=bot_headers).json()["data"]
    assert [p["id"] for p in projects] == [kept]

    # Editing the scope while the project is away, from what the user sees,
    # does not quietly take it out for good.
    r = _update(client, owner, bot["id"], {"scope": _scope([kept], ALL_PERMISSIONS)})
    assert r.json()["scope"]["project_ids"] == [kept]

    entry = next(
        e
        for e in client.get(f"{API}/activity-log/", headers=owner).json()["data"]
        if e["action"] == "project_deleted"
    )
    r = client.post(f"{API}/activity-log/{entry['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    assert set(_listed(client, owner)[0]["scope"]["project_ids"]) == {kept, deleted}
    assert client.get(f"{API}/tasks/{task_id}", headers=bot_headers).status_code == 200


def test_only_the_owner_edits_a_bot_user(
    client: TestClient, db: Session, owner: Headers
) -> None:
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    other = create_user_headers(client, db)

    r = _update(client, other, bot["id"], {"name": "Taken over"})
    assert r.status_code == 404
    r = _update(client, owner, str(uuid.uuid4()), {"name": "Nobody"})
    assert r.status_code == 404
    assert _listed(client, owner)[0]["name"] == bot["name"]


# --- Deleting -----------------------------------------------------------------


def test_deleting_a_bot_user_marks_it_deleted_and_takes_it_off_the_list(
    client: TestClient, db: Session, owner: Headers
) -> None:
    kept = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    deleted = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY, name="Retired"
    )

    r = client.delete(f"{API}/bot-users/{deleted['id']}", headers=owner)
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/bot-users/", headers=owner)
    assert [b["id"] for b in r.json()["data"]] == [kept["id"]]
    assert r.json()["count"] == 1
    stored = db.get(BotUser, uuid.UUID(deleted["id"]))
    assert stored is not None
    db.refresh(stored)
    assert stored.deleted_at is not None
    assert stored.name == "Retired"


def test_a_deleted_bot_user_is_gone_from_every_management_endpoint(
    client: TestClient, owner: Headers
) -> None:
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)

    base = f"{API}/bot-users/{bot['id']}"
    assert client.delete(base, headers=owner).status_code == 404
    assert client.patch(base, headers=owner, json={"name": "Back"}).status_code == 404
    assert client.post(f"{base}/token", headers=owner).status_code == 404
    assert client.delete(f"{base}/token", headers=owner).status_code == 404


def test_a_deleted_bot_users_token_is_refused_before_its_scope_is_considered(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot_headers = token_headers(client, owner, bot["id"])
    assert client.get(f"{API}/tasks/{task_id}", headers=bot_headers).status_code == 200

    client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)

    unknown = {"Authorization": "Bearer taskly_bot_" + "x" * 43}
    for method, path in (
        ("GET", f"{API}/tasks/{task_id}"),
        ("GET", f"{API}/tasks/"),
        ("POST", f"{API}/bot-users/"),
    ):
        r = client.request(method, path, headers=bot_headers)
        assert r.status_code == 401, r.text
        assert r.text == client.request(method, path, headers=unknown).text


def test_tasks_assigned_to_a_deleted_bot_user_stay_assigned_to_it(
    client: TestClient, owner: Headers
) -> None:
    bot = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY, name="Retired"
    )
    task_id = client.post(
        f"{API}/tasks/", headers=owner, json={"title": "T", "assignee_id": bot["id"]}
    ).json()["id"]

    client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)

    task = client.get(f"{API}/tasks/{task_id}", headers=owner).json()
    assert task["assignee_id"] == bot["id"]
    assert task["assignee_bot_user"] == {
        "id": bot["id"],
        "name": "Retired",
        "deleted": True,
    }


def test_activity_entries_made_by_a_deleted_bot_user_still_name_it(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Retired",
    )
    bot_headers = token_headers(client, owner, bot["id"])
    task_id = create_task(client, bot_headers, project_id=project_id)

    client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    created = next(
        e
        for e in entries
        if e["entity_id"] == task_id and e["action"] == "task_created"
    )
    assert created["actor_bot_user_id"] == bot["id"]
    assert created["actor_bot_user_name"] == "Retired"


def test_only_the_owner_deletes_a_bot_user(
    client: TestClient, db: Session, owner: Headers
) -> None:
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    bot_headers = token_headers(client, owner, bot["id"])
    other = create_user_headers(client, db)

    assert (
        client.delete(f"{API}/bot-users/{bot['id']}", headers=other).status_code == 404
    )
    assert client.get(f"{API}/tasks/", headers=bot_headers).status_code == 200
    assert [b["id"] for b in _listed(client, owner)] == [bot["id"]]


def test_a_bot_cannot_edit_or_delete_bot_users_itself_included(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    other_bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)
    bot_headers = token_headers(client, owner, bot["id"])

    for target in (bot["id"], other_bot["id"]):
        r = _update(
            client,
            bot_headers,
            target,
            {"name": "Mine now", "scope": _scope([project_id], ALL_PERMISSIONS)},
        )
        assert r.status_code == 403
        assert error_code(r) == "human_only"
        r = client.delete(f"{API}/bot-users/{target}", headers=bot_headers)
        assert r.status_code == 403
        assert error_code(r) == "human_only"

    assert {b["name"] for b in _listed(client, owner)} == {bot["name"]}
    assert len(_listed(client, owner)) == 2
