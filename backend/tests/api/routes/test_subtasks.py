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


def _create_task(
    client: TestClient, headers: dict[str, str], title: str, **fields: object
) -> dict:
    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": title, **fields},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _read_task(client: TestClient, headers: dict[str, str], task_id: str) -> dict:
    r = client.get(f"{settings.API_V1_STR}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _complete(
    client: TestClient, headers: dict[str, str], task_id: str, **fields: object
):
    return client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=headers,
        json={"status": "done", **fields},
    )


def test_task_can_be_nested_to_arbitrary_depth(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])
    great_grandchild = _create_task(
        client, headers, "Great grandchild", parent_id=grandchild["id"]
    )

    assert root["parent_id"] is None
    assert child["parent_id"] == root["id"]
    assert grandchild["parent_id"] == child["id"]
    assert great_grandchild["parent_id"] == grandchild["id"]


def test_subtask_is_a_full_task(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")

    subtask = _create_task(
        client,
        headers,
        "Subtask",
        parent_id=root["id"],
        description="Details",
        due_date="2026-01-01",
        priority="P1",
    )
    assert subtask["description"] == "Details"
    assert subtask["due_date"] == "2026-01-01"
    assert subtask["priority"] == "P1"
    assert subtask["status"] == "todo"

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{subtask['id']}",
        headers=headers,
        json={"title": "Renamed subtask", "status": "done"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed subtask"
    assert r.json()["status"] == "done"


def test_subtask_resolves_to_the_project_of_its_root_ancestor(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Work")

    root = _create_task(client, headers, "Root", project_id=project_id)
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])

    assert child["project_id"] == project_id
    assert grandchild["project_id"] == project_id
    assert _read_task(client, headers, grandchild["id"])["project_id"] == project_id

    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers)
    listed = {t["title"]: t["project_id"] for t in r.json()["data"]}
    assert listed == {
        "Root": project_id,
        "Child": project_id,
        "Grandchild": project_id,
    }


def test_subtask_cannot_be_given_its_own_project(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    other_project_id = _create_project(client, headers, "Elsewhere")
    root = _create_task(client, headers, "Root")

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={
            "title": "Child",
            "parent_id": root["id"],
            "project_id": other_project_id,
        },
    )
    assert r.status_code == 400


def test_subtask_cannot_be_moved_to_another_project(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    other_project_id = _create_project(client, headers, "Elsewhere")
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{child['id']}",
        headers=headers,
        json={"project_id": other_project_id},
    )
    assert r.status_code == 400
    assert _read_task(client, headers, child["id"])["project_id"] == _inbox_id(
        client, headers
    )


def test_moving_a_root_task_moves_its_whole_subtree(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    inbox_id = _inbox_id(client, headers)
    work_id = _create_project(client, headers, "Work")

    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])
    assert grandchild["project_id"] == inbox_id

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{root['id']}",
        headers=headers,
        json={"project_id": work_id},
    )
    assert r.status_code == 200
    assert r.json()["project_id"] == work_id

    assert _read_task(client, headers, child["id"])["project_id"] == work_id
    assert _read_task(client, headers, grandchild["id"])["project_id"] == work_id


def test_subtask_of_another_users_task_is_rejected(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    root = _create_task(client, headers_a, "A's task")

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers_b,
        json={"title": "Sneaky child", "parent_id": root["id"]},
    )
    assert r.status_code == 404


def test_unknown_parent_is_rejected(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Orphan", "parent_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


def test_completing_a_task_with_uncompleted_subtasks_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    _create_task(client, headers, "Child", parent_id=root["id"])

    r = _complete(client, headers, root["id"])
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "task_has_uncompleted_subtasks"
    assert _read_task(client, headers, root["id"])["status"] == "todo"


def test_refusal_looks_at_the_whole_subtree(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])

    r = _complete(client, headers, child["id"], subtasks="leave_uncompleted")
    assert r.status_code == 200

    r = _complete(client, headers, root["id"])
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "task_has_uncompleted_subtasks"
    assert _read_task(client, headers, grandchild["id"])["status"] == "todo"


def test_refusal_is_distinct_from_other_client_errors(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    other_project_id = _create_project(client, headers, "Elsewhere")
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])

    refusal = _complete(client, headers, root["id"])
    move = client.patch(
        f"{settings.API_V1_STR}/tasks/{child['id']}",
        headers=headers,
        json={"project_id": other_project_id},
    )
    assert refusal.status_code != move.status_code
    assert refusal.status_code == 409


def test_completing_with_subtasks_left_uncompleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])

    r = _complete(client, headers, root["id"], subtasks="leave_uncompleted")
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    assert _read_task(client, headers, child["id"])["status"] == "todo"
    assert _read_task(client, headers, grandchild["id"])["status"] == "todo"


def test_completing_with_subtasks_completed_too(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])

    r = _complete(client, headers, root["id"], subtasks="complete")
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    assert _read_task(client, headers, child["id"])["status"] == "done"
    assert _read_task(client, headers, grandchild["id"])["status"] == "done"


def test_completing_every_subtask_leaves_the_parent_uncompleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    first = _create_task(client, headers, "First", parent_id=root["id"])
    second = _create_task(client, headers, "Second", parent_id=root["id"])

    for task in (first, second):
        r = _complete(client, headers, task["id"])
        assert r.status_code == 200

    assert _read_task(client, headers, root["id"])["status"] == "todo"


def test_completing_a_parent_whose_subtasks_are_done_needs_no_directive(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    _complete(client, headers, child["id"])

    r = _complete(client, headers, root["id"])
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_returning_a_task_to_not_completed_is_never_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    _create_task(client, headers, "Child", parent_id=root["id"])
    _complete(client, headers, root["id"], subtasks="leave_uncompleted")

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{root['id']}",
        headers=headers,
        json={"status": "todo"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "todo"


def test_editing_a_parent_without_completing_it_is_never_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    _create_task(client, headers, "Child", parent_id=root["id"])

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{root['id']}",
        headers=headers,
        json={"title": "Renamed"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"


def test_subtask_directive_without_completion_is_rejected(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    _create_task(client, headers, "Child", parent_id=root["id"])

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{root['id']}",
        headers=headers,
        json={"title": "Renamed", "subtasks": "complete"},
    )
    assert r.status_code == 400
    assert _read_task(client, headers, root["id"])["title"] == "Root"
