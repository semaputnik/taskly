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


def _inbox_id(client: TestClient, headers: dict[str, str]) -> str:
    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    return next(p["id"] for p in r.json()["data"] if p["is_inbox"])


def _create_project(client: TestClient, headers: dict[str, str], name: str) -> str:
    r = client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers,
        json={"name": name},
    )
    return r.json()["id"]


def test_create_task_without_project_lands_in_inbox(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    inbox_id = _inbox_id(client, headers)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Buy milk"},
    )
    assert r.status_code == 200
    task = r.json()
    assert task["title"] == "Buy milk"
    assert task["project_id"] == inbox_id
    assert task["status"] == "todo"
    assert task["priority"] is None
    assert task["due_date"] is None


def test_create_task_in_explicit_project(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Groceries")

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Buy milk", "project_id": project_id},
    )
    assert r.status_code == 200
    assert r.json()["project_id"] == project_id


def test_create_task_requires_title(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={},
    )
    assert r.status_code == 422


def test_due_date_round_trips_without_timezone_shift(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "File taxes", "due_date": "2026-01-01"},
    )
    assert r.status_code == 200
    assert r.json()["due_date"] == "2026-01-01"


def test_priority_rejects_invalid_value(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Bad priority", "priority": "P5"},
    )
    assert r.status_code == 422


def test_priority_ordering_treats_unset_as_p4(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    for title, priority in [
        ("no priority task", None),
        ("p4 task", "P4"),
        ("p1 task", "P1"),
        ("p3 task", "P3"),
    ]:
        payload: dict[str, str] = {"title": title}
        if priority is not None:
            payload["priority"] = priority
        client.post(f"{settings.API_V1_STR}/tasks/", headers=headers, json=payload)

    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers)
    titles = [t["title"] for t in r.json()["data"]]

    assert titles.index("p1 task") < titles.index("p3 task")
    assert titles.index("p3 task") < titles.index("p4 task")
    assert titles.index("p3 task") < titles.index("no priority task")

    no_priority_task = next(
        t for t in r.json()["data"] if t["title"] == "no priority task"
    )
    assert no_priority_task["priority"] is None


def test_complete_and_return_to_not_completed(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Do the thing"},
    )
    task_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"status": "done"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"status": "todo"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "todo"


def test_move_task_between_projects(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    other_project_id = _create_project(client, headers, "Work")

    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Move me"},
    )
    task_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"project_id": other_project_id},
    )
    assert r.status_code == 200
    assert r.json()["project_id"] == other_project_id


def test_cannot_move_task_to_project_not_owned(client: TestClient, db: Session) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    other_project_id = _create_project(client, headers_b, "B's project")

    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers_a,
        json={"title": "Stay put"},
    )
    task_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers_a,
        json={"project_id": other_project_id},
    )
    assert r.status_code == 404


def test_cannot_unset_task_project(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Needs a home"},
    )
    task_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"project_id": None},
    )
    assert r.status_code == 400


def test_assign_task_to_self_and_unassign(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=headers)
    user_id = r.json()["id"]

    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Assign me"},
    )
    task_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"assignee_id": user_id},
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] == user_id

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"assignee_id": None},
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] is None


def test_cannot_assign_task_to_another_user(client: TestClient, db: Session) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=headers_b)
    other_user_id = r.json()["id"]

    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers_a,
        json={"title": "Mine only"},
    )
    task_id = create_r.json()["id"]

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers_a,
        json={"assignee_id": other_user_id},
    )
    assert r.status_code == 400


def test_users_cannot_see_other_users_tasks(client: TestClient, db: Session) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)

    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers_a,
        json={"title": "User A's task"},
    )
    task_id = create_r.json()["id"]

    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers_b)
    titles = {t["title"] for t in r.json()["data"]}
    assert "User A's task" not in titles

    r = client.get(f"{settings.API_V1_STR}/tasks/{task_id}", headers=headers_b)
    assert r.status_code == 404

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers_b,
        json={"title": "Hijacked"},
    )
    assert r.status_code == 404


def test_nonexistent_task_returns_404(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(f"{settings.API_V1_STR}/tasks/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{uuid.uuid4()}",
        headers=headers,
        json={"title": "Anything"},
    )
    assert r.status_code == 404


def test_view_and_list_task(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    create_r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Viewable", "description": "Details"},
    )
    task_id = create_r.json()["id"]

    r = client.get(f"{settings.API_V1_STR}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Viewable"
    assert r.json()["description"] == "Details"

    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers)
    assert r.status_code == 200
    assert r.json()["count"] == 1
