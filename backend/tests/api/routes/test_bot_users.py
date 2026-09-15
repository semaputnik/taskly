import hashlib
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core import security
from app.core.config import settings
from app.main import app
from app.models import BotUser, UserCreate
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR

ALL_PERMISSIONS = {
    "create_tasks": True,
    "read_tasks": True,
    "update_tasks": True,
    "delete_tasks": True,
    "add_comments": True,
}
READ_ONLY = {"read_tasks": True}


def _new_user(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    r = client.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _project(client: TestClient, headers: dict[str, str], name: str = "P") -> str:
    r = client.post(f"{API}/projects/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    project_id: str = r.json()["id"]
    return project_id


def _task(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_id: str | None = None,
    parent_id: str | None = None,
    title: str = "T",
) -> str:
    body: dict[str, Any] = {"title": title}
    if project_id:
        body["project_id"] = project_id
    if parent_id:
        body["parent_id"] = parent_id
    r = client.post(f"{API}/tasks/", headers=headers, json=body)
    assert r.status_code == 200, r.text
    task_id: str = r.json()["id"]
    return task_id


def _create_bot(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_ids: list[str],
    permissions: dict[str, bool],
    name: str = "Triage agent",
) -> dict[str, Any]:
    r = client.post(
        f"{API}/bot-users/",
        headers=headers,
        json={
            "name": name,
            "scope": {"project_ids": project_ids, "permissions": permissions},
        },
    )
    assert r.status_code == 200, r.text
    bot: dict[str, Any] = r.json()
    return bot


def _bot_headers(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_ids: list[str],
    permissions: dict[str, bool],
) -> dict[str, str]:
    bot = _create_bot(client, headers, project_ids=project_ids, permissions=permissions)
    r = client.post(f"{API}/bot-users/{bot['id']}/token", headers=headers)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _code(r: Any) -> str | None:
    detail = r.json().get("detail")
    return detail.get("code") if isinstance(detail, dict) else None


# --- Creating a bot user and issuing its token --------------------------------


def test_a_user_creates_a_bot_user_with_its_scope(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    project_id = _project(client, headers)

    bot = _create_bot(
        client,
        headers,
        project_ids=[project_id],
        permissions={"read_tasks": True, "add_comments": True},
    )
    assert bot["name"] == "Triage agent"
    assert bot["scope"] == {
        "project_ids": [project_id],
        "permissions": {
            "create_tasks": False,
            "read_tasks": True,
            "update_tasks": False,
            "delete_tasks": False,
            "add_comments": True,
        },
    }
    assert bot["has_token"] is False

    r = client.get(f"{API}/bot-users/", headers=headers)
    assert [b["id"] for b in r.json()["data"]] == [bot["id"]]
    assert r.json()["data"][0]["scope"] == bot["scope"]


def test_the_scope_has_no_all_projects_value_and_no_grants_that_are_never_allowed(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)

    bot = _create_bot(client, headers, project_ids=[], permissions=ALL_PERMISSIONS)
    assert bot["scope"]["project_ids"] == []
    assert set(bot["scope"]["permissions"]) == set(ALL_PERMISSIONS)


@pytest.mark.parametrize("name", ["", "   "])
def test_a_bot_user_needs_a_name(client: TestClient, db: Session, name: str) -> None:
    headers = _new_user(client, db)
    r = client.post(
        f"{API}/bot-users/",
        headers=headers,
        json={"name": name, "scope": {"project_ids": [], "permissions": {}}},
    )
    assert r.status_code == 422


def test_a_scope_can_only_name_projects_of_the_owner(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    other_project = _project(client, _new_user(client, db))

    for project_id in (other_project, str(uuid.uuid4())):
        r = client.post(
            f"{API}/bot-users/",
            headers=headers,
            json={
                "name": "Bot",
                "scope": {"project_ids": [project_id], "permissions": READ_ONLY},
            },
        )
        assert r.status_code == 404
    assert client.get(f"{API}/bot-users/", headers=headers).json()["count"] == 0


def test_the_token_is_returned_once_and_stored_only_as_a_digest(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    bot = _create_bot(client, headers, project_ids=[], permissions=READ_ONLY)

    r = client.post(f"{API}/bot-users/{bot['id']}/token", headers=headers)
    assert r.status_code == 200
    token = r.json()["token"]
    assert token.startswith("taskly_bot_")

    # Nothing hands it back afterwards: not the list, not a second issue.
    listed = client.get(f"{API}/bot-users/", headers=headers)
    assert token not in listed.text
    assert listed.json()["data"][0]["has_token"] is True
    r = client.post(f"{API}/bot-users/{bot['id']}/token", headers=headers)
    assert r.status_code == 409
    assert _code(r) == "token_already_issued"
    assert token not in r.text

    stored = db.get(BotUser, uuid.UUID(bot["id"]))
    assert stored is not None
    db.refresh(stored)
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in {stored.token_hash, stored.name}


def test_a_user_only_sees_and_manages_their_own_bot_users(
    client: TestClient, db: Session
) -> None:
    owner = _new_user(client, db)
    other = _new_user(client, db)
    bot = _create_bot(client, owner, project_ids=[], permissions=READ_ONLY)

    assert client.get(f"{API}/bot-users/", headers=other).json()["count"] == 0
    r = client.post(f"{API}/bot-users/{bot['id']}/token", headers=other)
    assert r.status_code == 404


def test_bot_users_are_not_accounts(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    headers = _new_user(client, db)
    bot = _create_bot(client, headers, project_ids=[], permissions=READ_ONLY)

    r = client.get(
        f"{API}/users/", headers=superuser_token_headers, params={"limit": 1000}
    )
    listed = {account["id"] for account in r.json()["data"]}
    assert bot["id"] not in listed
    assert bot["name"] not in r.text


# --- Authentication -----------------------------------------------------------

# Everything a bot user can call. Every other endpoint that needs credentials
# takes a human, so a new endpoint stays out of a bot's reach until it is
# deliberately opened here.
BOT_REACHABLE = {
    f"GET {API}/tasks/",
    f"GET {API}/tasks/{{task_id}}",
    f"GET {API}/projects/",
}


def _authenticated_routes() -> list[tuple[str, str]]:
    return sorted(
        (method, path)
        for path, operations in app.openapi()["paths"].items()
        for method, operation in operations.items()
        if operation.get("security")
    )


def test_the_bot_reachable_routes_exist() -> None:
    routes = {f"{method.upper()} {path}" for method, path in _authenticated_routes()}
    assert BOT_REACHABLE <= routes


@pytest.mark.parametrize(
    ("method", "path"),
    [
        route
        for route in _authenticated_routes()
        if f"{route[0].upper()} {route[1]}" not in BOT_REACHABLE
    ],
    ids=lambda value: value,
)
def test_a_bot_token_is_refused_by_every_human_only_endpoint(
    client: TestClient, db: Session, method: str, path: str
) -> None:
    headers = _new_user(client, db)
    project_id = _project(client, headers)
    bot_headers = _bot_headers(
        client, headers, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    # Called with ids that exist nowhere: the refusal must come before any
    # lookup, for what the caller is.
    url = path.format(**{name: uuid.uuid4() for name in _path_params(path)})
    r = client.request(method, url, headers=bot_headers)
    assert r.status_code == 403, r.text
    assert _code(r) == "human_only"


def _path_params(path: str) -> list[str]:
    return [part[1:-1] for part in path.split("/") if part.startswith("{")]


def test_a_bot_cannot_create_or_configure_bot_users_whatever_it_is_granted(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    project_id = _project(client, headers)
    bot = _create_bot(
        client, headers, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    token = client.post(f"{API}/bot-users/{bot['id']}/token", headers=headers).json()[
        "token"
    ]
    bot_headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"{API}/bot-users/",
        headers=bot_headers,
        json={
            "name": "Spawned",
            "scope": {"project_ids": [project_id], "permissions": ALL_PERMISSIONS},
        },
    )
    assert r.status_code == 403
    assert _code(r) == "human_only"
    # Not even for itself.
    r = client.post(f"{API}/bot-users/{bot['id']}/token", headers=bot_headers)
    assert r.status_code == 403
    assert _code(r) == "human_only"
    assert client.get(f"{API}/bot-users/", headers=headers).json()["count"] == 1


def test_a_bot_token_authenticates_bot_reachable_endpoints(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    project_id = _project(client, headers)
    bot_headers = _bot_headers(
        client, headers, project_ids=[project_id], permissions=READ_ONLY
    )

    assert client.get(f"{API}/tasks/", headers=bot_headers).status_code == 200
    assert client.get(f"{API}/projects/", headers=bot_headers).status_code == 200


def test_a_human_jwt_is_not_a_bot_token(client: TestClient, db: Session) -> None:
    headers = _new_user(client, db)
    bot = _create_bot(client, headers, project_ids=[], permissions=READ_ONLY)

    # A well-signed session token that names the bot user's id resolves to no
    # one: bot users are not reachable through the human session at all.
    forged = security.create_access_token(bot["id"], timedelta(minutes=5))
    r = client.get(f"{API}/tasks/", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


@pytest.mark.parametrize(
    "token",
    ["taskly_bot_" + "x" * 43, "taskly_bot_", "not-a-token"],
    ids=["unknown bot token", "bare prefix", "garbage"],
)
def test_a_token_that_matches_no_bot_user_is_refused(
    client: TestClient, token: str
) -> None:
    r = client.get(f"{API}/tasks/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (401, 403)
    assert _code(r) is None


# --- Reading tasks within the scope -------------------------------------------


def test_a_bot_lists_only_the_tasks_of_projects_in_its_scope(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    scoped = _project(client, headers, "Scoped")
    unscoped = _project(client, headers, "Unscoped")
    root = _task(client, headers, project_id=scoped)
    child = _task(client, headers, parent_id=root)
    grandchild = _task(client, headers, parent_id=child)
    _task(client, headers, project_id=unscoped)
    outside_child = _task(
        client, headers, parent_id=_task(client, headers, project_id=unscoped)
    )
    _task(client, headers)  # Inbox, not in scope either
    bot_headers = _bot_headers(
        client, headers, project_ids=[scoped], permissions=READ_ONLY
    )

    r = client.get(f"{API}/tasks/", headers=bot_headers)
    assert r.status_code == 200
    assert {t["id"] for t in r.json()["data"]} == {root, child, grandchild}
    assert r.json()["count"] == 3
    assert outside_child not in r.text

    # The existing filters narrow within the scope.
    r = client.get(f"{API}/tasks/", headers=bot_headers, params={"project_id": scoped})
    assert {t["id"] for t in r.json()["data"]} == {root, child, grandchild}


def test_a_bot_reads_a_task_and_a_subtask_in_its_scope(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    scoped = _project(client, headers)
    root = _task(client, headers, project_id=scoped, title="Root")
    child = _task(client, headers, parent_id=root, title="Child")
    bot_headers = _bot_headers(
        client, headers, project_ids=[scoped], permissions=READ_ONLY
    )

    r = client.get(f"{API}/tasks/{root}", headers=bot_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Root"
    r = client.get(f"{API}/tasks/{child}", headers=bot_headers)
    assert r.status_code == 200
    assert r.json()["project_id"] == scoped


def test_outside_the_scope_is_a_scope_error_not_a_missing_task(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    scoped = _project(client, headers)
    unscoped = _project(client, headers)
    outside_root = _task(client, headers, project_id=unscoped)
    outside_child = _task(client, headers, parent_id=outside_root)
    bot_headers = _bot_headers(
        client, headers, project_ids=[scoped], permissions=ALL_PERMISSIONS
    )

    for task_id in (outside_root, outside_child):
        r = client.get(f"{API}/tasks/{task_id}", headers=bot_headers)
        assert r.status_code == 403
        assert _code(r) == "outside_scope"

    r = client.get(
        f"{API}/tasks/", headers=bot_headers, params={"project_id": unscoped}
    )
    assert r.status_code == 403
    assert _code(r) == "outside_scope"

    r = client.get(f"{API}/tasks/{uuid.uuid4()}", headers=bot_headers)
    assert r.status_code == 404
    r = client.get(
        f"{API}/tasks/", headers=bot_headers, params={"project_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404


def test_a_bot_without_task_read_is_refused_even_in_its_scope(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    scoped = _project(client, headers)
    task_id = _task(client, headers, project_id=scoped)
    everything_but_read = {**ALL_PERMISSIONS, "read_tasks": False}
    bot_headers = _bot_headers(
        client, headers, project_ids=[scoped], permissions=everything_but_read
    )

    for url, params in (
        (f"{API}/tasks/", {}),
        (f"{API}/tasks/", {"project_id": scoped}),
        (f"{API}/tasks/{task_id}", {}),
    ):
        r = client.get(url, headers=bot_headers, params=params)
        assert r.status_code == 403, url
        assert _code(r) == "permission_not_granted"


@pytest.mark.parametrize("in_scope", [True, False], ids=["in scope", "out of scope"])
def test_an_archived_project_is_refused_before_the_scope_is_considered(
    client: TestClient, db: Session, in_scope: bool
) -> None:
    headers = _new_user(client, db)
    live = _project(client, headers, "Live")
    archived = _project(client, headers, "Archived")
    root = _task(client, headers, project_id=archived)
    child = _task(client, headers, parent_id=root)
    live_task = _task(client, headers, project_id=live)
    bot_headers = _bot_headers(
        client,
        headers,
        project_ids=[live, archived] if in_scope else [live],
        permissions=ALL_PERMISSIONS,
    )
    r = client.post(f"{API}/projects/{archived}/archive", headers=headers)
    assert r.status_code == 200

    for task_id in (root, child):
        r = client.get(f"{API}/tasks/{task_id}", headers=bot_headers)
        assert r.status_code == 403
        assert _code(r) == "project_archived"
    r = client.get(
        f"{API}/tasks/", headers=bot_headers, params={"project_id": archived}
    )
    assert r.status_code == 403
    assert _code(r) == "project_archived"

    r = client.get(f"{API}/tasks/", headers=bot_headers)
    assert {t["id"] for t in r.json()["data"]} == {live_task}
    for url in (f"{API}/tasks/", f"{API}/projects/"):
        r = client.get(url, headers=bot_headers, params={"archived": True})
        assert r.status_code == 403
        assert _code(r) == "project_archived"

    # The owner still reads it: the archive is closed to bots, not to them.
    assert client.get(f"{API}/tasks/{root}", headers=headers).status_code == 200


def test_a_bot_lists_only_the_projects_in_its_scope(
    client: TestClient, db: Session
) -> None:
    headers = _new_user(client, db)
    scoped = _project(client, headers, "Scoped")
    _project(client, headers, "Unscoped")
    # Scope needs no task permission to list what it names (FR-08.9).
    bot_headers = _bot_headers(client, headers, project_ids=[scoped], permissions={})

    r = client.get(f"{API}/projects/", headers=bot_headers)
    assert r.status_code == 200
    assert [p["id"] for p in r.json()["data"]] == [scoped]
    assert r.json()["count"] == 1


def test_a_bot_never_reaches_another_users_data(
    client: TestClient, db: Session
) -> None:
    owner = _new_user(client, db)
    other = _new_user(client, db)
    other_project = _project(client, other)
    other_task = _task(client, other, project_id=other_project)
    bot_headers = _bot_headers(
        client, owner, project_ids=[_project(client, owner)], permissions=READ_ONLY
    )

    r = client.get(f"{API}/tasks/{other_task}", headers=bot_headers)
    assert r.status_code == 404
    r = client.get(
        f"{API}/tasks/", headers=bot_headers, params={"project_id": other_project}
    )
    assert r.status_code == 404
    assert other_task not in client.get(f"{API}/tasks/", headers=bot_headers).text
    assert other_project not in client.get(f"{API}/projects/", headers=bot_headers).text
