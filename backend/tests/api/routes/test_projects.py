import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
from tests.utils.utils import random_email, random_lower_string


def _headers_for_new_user(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    crud.create_user(session=db, user_create=user_in)

    login_data = {"username": email, "password": password}
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_new_account_gets_inbox_project(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["data"][0]["name"] == "Inbox"
    assert data["data"][0]["is_inbox"] is True


def test_create_project(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers,
        json={"name": "Groceries", "description": "Weekly shopping list"},
    )
    assert r.status_code == 200
    created = r.json()
    assert created["name"] == "Groceries"
    assert created["description"] == "Weekly shopping list"
    assert created["is_inbox"] is False


def test_list_projects_includes_inbox_and_created(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers,
        json={"name": "Groceries"},
    )

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    names = {p["name"] for p in data["data"]}
    assert names == {"Inbox", "Groceries"}


def test_rename_project(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    create_r = client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers,
        json={"name": "Old name"},
    )
    project_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/projects/{project_id}",
        headers=headers,
        json={"name": "New name", "description": "New description"},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["name"] == "New name"
    assert updated["description"] == "New description"


def test_users_cannot_see_other_users_projects(client: TestClient, db: Session) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)

    create_r = client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers_a,
        json={"name": "User A's project"},
    )
    project_id = create_r.json()["id"]

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers_b)
    names = {p["name"] for p in r.json()["data"]}
    assert "User A's project" not in names

    r = client.patch(
        f"{settings.API_V1_STR}/projects/{project_id}",
        headers=headers_b,
        json={"name": "Hijacked"},
    )
    assert r.status_code == 404

    r = client.delete(
        f"{settings.API_V1_STR}/projects/{project_id}",
        headers=headers_b,
    )
    assert r.status_code == 404


def test_nonexistent_project_returns_404(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.patch(
        f"{settings.API_V1_STR}/projects/{uuid.uuid4()}",
        headers=headers,
        json={"name": "Anything"},
    )
    assert r.status_code == 404


def test_renaming_inbox_is_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    inbox_id = next(p["id"] for p in r.json()["data"] if p["is_inbox"])

    r = client.patch(
        f"{settings.API_V1_STR}/projects/{inbox_id}",
        headers=headers,
        json={"name": "Not Inbox"},
    )
    assert r.status_code == 400
    assert "renamed" in r.json()["detail"].lower()


def test_changing_inbox_description_is_allowed(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    inbox_id = next(p["id"] for p in r.json()["data"] if p["is_inbox"])

    r = client.patch(
        f"{settings.API_V1_STR}/projects/{inbox_id}",
        headers=headers,
        json={"description": "Everything lands here"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Everything lands here"


def test_deleting_inbox_is_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    inbox_id = next(p["id"] for p in r.json()["data"] if p["is_inbox"])

    r = client.delete(f"{settings.API_V1_STR}/projects/{inbox_id}", headers=headers)
    assert r.status_code == 400
    assert "deleted" in r.json()["detail"].lower()


def test_delete_non_inbox_project(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    create_r = client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers,
        json={"name": "Throwaway"},
    )
    project_id = create_r.json()["id"]

    r = client.delete(f"{settings.API_V1_STR}/projects/{project_id}", headers=headers)
    assert r.status_code == 200

    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    names = {p["name"] for p in r.json()["data"]}
    assert "Throwaway" not in names
