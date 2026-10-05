"""
The test account builder: one place to set up a user with a session, projects
(archived ones too), trees of tasks (recurring ones too), bot users with a scope
and a token, and deleted tasks and projects, for tests.

Everything here goes through the API, so a fixture is built the way a client
builds it and the behaviour under test is the real one. A test that needs speed
over fidelity builds through `crud` itself (see `tests/utils/user.py`).
"""

from datetime import date
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.user import new_user_headers

API = settings.API_V1_STR

ALL_PERMISSIONS = {
    "create_tasks": True,
    "read_tasks": True,
    "update_tasks": True,
    "delete_tasks": True,
    "add_comments": True,
    "create_tags": True,
}
READ_ONLY = {"read_tasks": True}


def create_user_headers(client: TestClient, db: Session) -> dict[str, str]:
    return new_user_headers(client, db)


def my_id(client: TestClient, headers: dict[str, str]) -> str:
    """The id of the user (or bot user) these headers sign in as."""
    r = client.get(f"{API}/users/me", headers=headers)
    assert r.status_code == 200, r.text
    user_id: str = r.json()["id"]
    return user_id


def create_project_record(
    client: TestClient, headers: dict[str, str], name: str = "P"
) -> dict[str, Any]:
    r = client.post(f"{API}/projects/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    project: dict[str, Any] = r.json()
    return project


def create_project(client: TestClient, headers: dict[str, str], name: str = "P") -> str:
    project_id: str = create_project_record(client, headers, name)["id"]
    return project_id


def inbox_project_id(client: TestClient, headers: dict[str, str]) -> str:
    r = client.get(f"{API}/projects/", headers=headers)
    return next(p["id"] for p in r.json()["data"] if p["is_inbox"])


def archive_project(
    client: TestClient, headers: dict[str, str], project_id: str
) -> httpx.Response:
    return client.post(f"{API}/projects/{project_id}/archive", headers=headers)


def unarchive_project(
    client: TestClient, headers: dict[str, str], project_id: str
) -> httpx.Response:
    return client.post(f"{API}/projects/{project_id}/unarchive", headers=headers)


def create_archived_project(
    client: TestClient, headers: dict[str, str], name: str = "Shelved"
) -> str:
    """A project that has been archived, for tests that need one on the shelf."""
    project_id = create_project(client, headers, name)
    r = archive_project(client, headers, project_id)
    assert r.status_code == 200, r.text
    return project_id


def delete_project(
    client: TestClient, headers: dict[str, str], project_id: str
) -> httpx.Response:
    return client.delete(f"{API}/projects/{project_id}", headers=headers)


def create_task(
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


def create_task_record(
    client: TestClient, headers: dict[str, str], title: str, **fields: object
) -> dict[str, Any]:
    """Create a task with any of its fields, and return the task as the API shows it."""
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": title, **fields})
    assert r.status_code == 200, r.text
    task: dict[str, Any] = r.json()
    return task


def create_task_tree(
    client: TestClient,
    headers: dict[str, str],
    *,
    depth: int,
    project_id: str | None = None,
) -> list[str]:
    """A chain of tasks, each the subtask of the one before; ids from the root down."""
    ids: list[str] = []
    for level in range(depth):
        ids.append(
            create_task(
                client,
                headers,
                project_id=project_id,
                parent_id=ids[-1] if ids else None,
                title=f"Level {level}",
            )
        )
    return ids


def create_recurring_task(
    client: TestClient,
    headers: dict[str, str],
    due: date,
    recurrence: dict[str, Any] | None = None,
    title: str = "Water the plants",
    **fields: object,
) -> dict[str, Any]:
    """A task that repeats (weekly unless told otherwise), with its first due date."""
    return create_task_record(
        client,
        headers,
        title,
        due_date=due.isoformat(),
        recurrence=recurrence or {"frequency": "weekly"},
        **fields,
    )


def delete_task(
    client: TestClient,
    headers: dict[str, str],
    task_id: str,
    **params: object,
) -> httpx.Response:
    return client.delete(f"{API}/tasks/{task_id}", headers=headers, params=params)


def create_bot_user(
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


def issue_bot_headers(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_ids: list[str],
    permissions: dict[str, bool],
) -> dict[str, str]:
    """A new bot user of the user's with this scope, as its token's headers."""
    bot = create_bot_user(
        client, headers, project_ids=project_ids, permissions=permissions
    )
    return token_headers(client, headers, bot["id"])


def token_headers(
    client: TestClient, headers: dict[str, str], bot_user_id: str
) -> dict[str, str]:
    """Issue the bot user's token, as the headers a request sends it in."""
    r = client.post(f"{API}/bot-users/{bot_user_id}/token", headers=headers)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def error_code(r: Any) -> str | None:
    detail = r.json().get("detail")
    return detail.get("code") if isinstance(detail, dict) else None
