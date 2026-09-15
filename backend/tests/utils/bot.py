"""Setting up users, projects, tasks and bot users over the API, for tests."""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
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


def create_user_headers(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    r = client.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def create_project(client: TestClient, headers: dict[str, str], name: str = "P") -> str:
    r = client.post(f"{API}/projects/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    project_id: str = r.json()["id"]
    return project_id


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
