import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


def _new_user(client: TestClient, db: Session) -> tuple[User, dict[str, str]]:
    email = random_email()
    password = random_lower_string()
    user = crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    r = client.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    return user, {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- The one thing a superuser can do -----------------------------------------


def test_the_superuser_can_list_registered_accounts(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    user, _ = _new_user(client, db)

    r = client.get(f"{API}/users/", headers=superuser_token_headers)
    assert r.status_code == 200
    emails = {account["email"] for account in r.json()["data"]}
    assert user.email in emails
    assert settings.FIRST_SUPERUSER in emails


def test_a_normal_user_cannot_list_accounts(client: TestClient, db: Session) -> None:
    _, headers = _new_user(client, db)

    r = client.get(f"{API}/users/", headers=headers)
    assert r.status_code == 403


def test_the_account_list_carries_account_fields_only(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    _, headers = _new_user(client, db)
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": "Private"})
    assert r.status_code == 200

    r = client.get(f"{API}/users/", headers=superuser_token_headers)
    for account in r.json()["data"]:
        assert set(account) == {
            "id",
            "email",
            "full_name",
            "is_active",
            "is_superuser",
            "created_at",
        }


# --- Everything else a template superuser could do is gone --------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/users/", {"email": "new@example.com", "password": "password123"}),
        ("GET", "/users/{user_id}", None),
        ("PATCH", "/users/{user_id}", {"full_name": "Renamed by admin"}),
        ("PATCH", "/users/{user_id}", {"is_superuser": True}),
        ("DELETE", "/users/{user_id}", None),
    ],
    ids=["create", "read", "update", "promote", "delete"],
)
def test_the_superuser_cannot_manage_other_accounts(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    method: str,
    path: str,
    body: dict | None,
) -> None:
    user, _ = _new_user(client, db)

    r = client.request(
        method,
        f"{API}{path.format(user_id=user.id)}",
        headers=superuser_token_headers,
        json=body,
    )
    assert r.status_code in (404, 405), r.text

    db.refresh(user)
    assert user.full_name is None
    assert user.is_superuser is False
    assert crud.get_user_by_email(session=db, email="new@example.com") is None


def test_updating_your_own_profile_cannot_make_you_a_superuser(
    client: TestClient, db: Session
) -> None:
    user, headers = _new_user(client, db)

    r = client.patch(
        f"{API}/users/me",
        headers=headers,
        json={"full_name": "Me", "is_superuser": True},
    )
    assert r.status_code == 200
    assert r.json()["is_superuser"] is False

    db.refresh(user)
    assert user.full_name == "Me"
    assert user.is_superuser is False


def test_registering_cannot_make_you_a_superuser(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    r = client.post(
        f"{API}/users/signup",
        json={"email": email, "password": random_lower_string(), "is_superuser": True},
    )
    assert r.status_code == 200
    assert r.json()["is_superuser"] is False

    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None and user.is_superuser is False


# --- Registration is open -----------------------------------------------------


def test_anyone_can_register_and_gets_an_inbox(client: TestClient) -> None:
    email = random_email()
    password = random_lower_string()

    # No token at all: nobody has to invite or approve the new account.
    r = client.post(f"{API}/users/signup", json={"email": email, "password": password})
    assert r.status_code == 200, r.text

    r = client.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"{API}/projects/", headers=headers)
    assert [p["name"] for p in r.json()["data"] if p["is_inbox"]] == ["Inbox"]


# --- The superuser is an ordinary user as well --------------------------------


def test_the_superuser_has_an_inbox_and_tasks_of_their_own(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/projects/", headers=superuser_token_headers)
    assert any(p["is_inbox"] for p in r.json()["data"])

    r = client.post(
        f"{API}/tasks/", headers=superuser_token_headers, json={"title": "Admin's own"}
    )
    assert r.status_code == 200
    task_id = r.json()["id"]

    r = client.get(f"{API}/tasks/{task_id}", headers=superuser_token_headers)
    assert r.status_code == 200


def test_the_superuser_cannot_reach_another_users_data(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    _, headers = _new_user(client, db)
    project = client.post(
        f"{API}/projects/", headers=headers, json={"name": "Private project"}
    ).json()
    task = client.post(
        f"{API}/tasks/",
        headers=headers,
        json={"title": "Private task", "project_id": project["id"]},
    ).json()

    r = client.get(f"{API}/tasks/{task['id']}", headers=superuser_token_headers)
    assert r.status_code == 404
    r = client.patch(
        f"{API}/tasks/{task['id']}",
        headers=superuser_token_headers,
        json={"title": "Seen"},
    )
    assert r.status_code == 404
    r = client.get(
        f"{API}/tasks/{task['id']}/comments/", headers=superuser_token_headers
    )
    assert r.status_code == 404

    r = client.get(
        f"{API}/projects/", headers=superuser_token_headers, params={"limit": 1000}
    )
    assert project["id"] not in {p["id"] for p in r.json()["data"]}
    r = client.get(
        f"{API}/tasks/",
        headers=superuser_token_headers,
        params={"project_id": project["id"]},
    )
    assert r.status_code == 404

    r = client.get(
        f"{API}/activity-log/", headers=superuser_token_headers, params={"limit": 200}
    )
    assert task["id"] not in {e["entity_id"] for e in r.json()["data"]}
