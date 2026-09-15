import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.api.deps import get_attachment_storage
from app.core.config import settings
from app.main import app
from app.models import UserCreate
from tests.api.routes.test_attachments import InMemoryAttachmentStorage
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


@pytest.fixture(autouse=True)
def storage():
    fake_storage = InMemoryAttachmentStorage()
    app.dependency_overrides[get_attachment_storage] = lambda: fake_storage
    yield fake_storage
    del app.dependency_overrides[get_attachment_storage]


def _headers_for_new_user(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    r = client.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_project(client: TestClient, headers: dict[str, str], name: str) -> dict:
    r = client.post(f"{API}/projects/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


def _create_task(
    client: TestClient, headers: dict[str, str], title: str, **fields: object
) -> dict:
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": title, **fields})
    assert r.status_code == 200, r.text
    return r.json()


def _delete_task(client: TestClient, headers: dict[str, str], task_id: str) -> dict:
    """Delete a task, its subtasks included, and return the deletion's entry."""
    r = client.delete(
        f"{API}/tasks/{task_id}",
        headers=headers,
        params={"delete_subtasks": True},
    )
    assert r.status_code == 200, r.text
    return _latest_entry(client, headers, "task_deleted", task_id)


def _latest_entry(
    client: TestClient, headers: dict[str, str], action: str, task_id: str
) -> dict:
    r = client.get(f"{API}/activity-log/", headers=headers, params={"limit": 200})
    return next(
        entry
        for entry in r.json()["data"]
        if entry["action"] == action and entry["entity_id"] == task_id
    )


def _restore(
    client: TestClient, headers: dict[str, str], entry: dict
) -> httpx.Response:
    return client.post(f"{API}/activity-log/{entry['id']}/restore", headers=headers)


def _visible_titles(client: TestClient, headers: dict[str, str]) -> set[str]:
    r = client.get(f"{API}/tasks/", headers=headers, params={"limit": 1000})
    return {task["title"] for task in r.json()["data"]}


# --- What comes back ----------------------------------------------------------


def test_restoring_brings_the_same_task_back(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    task = _create_task(
        client,
        headers,
        "Fix the tap",
        project_id=project["id"],
        tags=["plumbing"],
        priority="P2",
    )
    r = client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=headers, json={"body": "Drips"}
    )
    assert r.status_code == 200
    r = client.post(
        f"{API}/tasks/{task['id']}/attachments/",
        headers=headers,
        files={"file": ("photo.jpg", b"jpeg", "image/jpeg")},
    )
    assert r.status_code == 200
    entry = _delete_task(client, headers, task["id"])
    assert entry["restorable"] is True

    r = _restore(client, headers, entry)
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json() == task
    comments = client.get(f"{API}/tasks/{task['id']}/comments/", headers=headers)
    assert [c["body"] for c in comments.json()["data"]] == ["Drips"]
    attachments = client.get(f"{API}/tasks/{task['id']}/attachments/", headers=headers)
    assert attachments.json()["count"] == 1


def test_restoring_a_task_brings_back_the_subtasks_deleted_with_it(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Move house")
    child = _create_task(client, headers, "Pack", parent_id=root["id"])
    _create_task(client, headers, "Books", parent_id=child["id"])
    entry = _delete_task(client, headers, root["id"])
    assert _visible_titles(client, headers) == set()

    r = _restore(client, headers, entry)
    assert r.status_code == 200, r.text

    assert _visible_titles(client, headers) == {"Move house", "Pack", "Books"}


def test_a_subtask_deleted_on_its_own_first_stays_deleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Move house")
    _create_task(client, headers, "Pack", parent_id=root["id"])
    dropped = _create_task(client, headers, "Hire a van", parent_id=root["id"])
    _create_task(client, headers, "Compare prices", parent_id=dropped["id"])

    # The order is the whole point: the subtask goes first, on its own.
    dropped_entry = _delete_task(client, headers, dropped["id"])
    root_entry = _delete_task(client, headers, root["id"])

    r = _restore(client, headers, root_entry)
    assert r.status_code == 200, r.text
    assert _visible_titles(client, headers) == {"Move house", "Pack"}

    # It still has its own deletion to come back from, under the restored
    # parent.
    r = _restore(client, headers, dropped_entry)
    assert r.status_code == 200, r.text
    assert _visible_titles(client, headers) == {
        "Move house",
        "Pack",
        "Hire a van",
        "Compare prices",
    }
    r = client.get(f"{API}/tasks/{dropped['id']}", headers=headers)
    assert r.json()["parent_id"] == root["id"]


# --- When a restore is refused ------------------------------------------------


def test_restoring_a_subtask_whose_parent_is_deleted_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Move house")
    child = _create_task(client, headers, "Pack", parent_id=root["id"])
    child_entry = _delete_task(client, headers, child["id"])
    _delete_task(client, headers, root["id"])

    r = _restore(client, headers, child_entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "parent_deleted"
    assert _visible_titles(client, headers) == set()


def test_restoring_a_task_whose_project_is_deleted_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Someday")
    task = _create_task(client, headers, "Learn the cello", project_id=project["id"])
    entry = _delete_task(client, headers, task["id"])
    r = client.delete(f"{API}/projects/{project['id']}", headers=headers)
    assert r.status_code == 200

    r = _restore(client, headers, entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "project_deleted"


def test_restoring_a_task_whose_project_is_archived_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Someday")
    task = _create_task(client, headers, "Learn the cello", project_id=project["id"])
    entry = _delete_task(client, headers, task["id"])
    r = client.post(f"{API}/projects/{project['id']}/archive", headers=headers)
    assert r.status_code == 200

    r = _restore(client, headers, entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "project_archived"

    r = client.post(f"{API}/projects/{project['id']}/unarchive", headers=headers)
    r = _restore(client, headers, entry)
    assert r.status_code == 200, r.text


def test_restoring_would_not_open_a_second_occurrence_of_the_same_series(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    first = _create_task(
        client,
        headers,
        "Water plants",
        due_date="2026-03-02",
        recurrence={"frequency": "weekly"},
    )
    r = client.patch(
        f"{API}/tasks/{first['id']}", headers=headers, json={"completed": True}
    )
    assert r.status_code == 200
    second = next(
        t
        for t in client.get(
            f"{API}/tasks/", headers=headers, params={"completed": False}
        ).json()["data"]
        if t["title"] == "Water plants"
    )
    entry = _delete_task(client, headers, second["id"])
    # The earlier occurrence is the latest one left, so it can be reopened.
    r = client.patch(
        f"{API}/tasks/{first['id']}", headers=headers, json={"completed": False}
    )
    assert r.status_code == 200, r.text

    r = _restore(client, headers, entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "series_has_open_occurrence"
    r = client.get(f"{API}/tasks/{second['id']}", headers=headers)
    assert r.status_code == 404


def test_restoring_a_task_deleted_again_since_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Call the bank")
    first_entry = _delete_task(client, headers, task["id"])
    assert _restore(client, headers, first_entry).status_code == 200
    second_entry = _delete_task(client, headers, task["id"])

    r = _restore(client, headers, first_entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "deleted_again"

    assert _restore(client, headers, second_entry).status_code == 200


# --- Idempotence, ownership, and the log --------------------------------------


def test_restoring_twice_changes_nothing_the_second_time(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Call the bank")
    entry = _delete_task(client, headers, task["id"])
    assert _restore(client, headers, entry).status_code == 200
    log_length = client.get(f"{API}/activity-log/", headers=headers).json()["count"]

    r = _restore(client, headers, entry)
    assert r.status_code == 200
    assert _visible_titles(client, headers) == {"Call the bank"}
    assert (
        client.get(f"{API}/activity-log/", headers=headers).json()["count"]
        == log_length
    )


def test_another_users_entry_cannot_be_restored(
    client: TestClient, db: Session
) -> None:
    owner = _headers_for_new_user(client, db)
    stranger = _headers_for_new_user(client, db)
    task = _create_task(client, owner, "Private")
    entry = _delete_task(client, owner, task["id"])

    r = _restore(client, stranger, entry)
    assert r.status_code == 404
    assert _visible_titles(client, owner) == set()


def test_only_a_deletion_entry_can_be_restored(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Call the bank")
    created = _latest_entry(client, headers, "task_created", task["id"])
    assert created["restorable"] is False

    r = _restore(client, headers, created)
    assert r.status_code == 400


def test_a_restore_is_logged_and_the_deletion_entry_is_left_as_it_was(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Move house")
    _create_task(client, headers, "Pack", parent_id=root["id"])
    entry = _delete_task(client, headers, root["id"])

    assert _restore(client, headers, entry).status_code == 200

    restored = _latest_entry(client, headers, "task_restored", root["id"])
    assert restored["deletion_id"] == entry["deletion_id"]
    assert restored["details"]["title"] == "Move house"
    assert restored["details"]["subtask_count"] == 1

    deleted = _latest_entry(client, headers, "task_deleted", root["id"])
    assert deleted["id"] == entry["id"]
    assert deleted["details"] == entry["details"]
    assert deleted["created_at"] == entry["created_at"]
    # Its rows are back, so there is nothing left to restore from it.
    assert deleted["restorable"] is False

    actions = [
        e["action"]
        for e in client.get(f"{API}/activity-log/", headers=headers).json()["data"]
    ]
    assert actions.count("task_restored") == 1


# --- Projects -----------------------------------------------------------------


def _delete_project(
    client: TestClient, headers: dict[str, str], project_id: str
) -> dict:
    """Delete a project and return the deletion's entry."""
    r = client.delete(f"{API}/projects/{project_id}", headers=headers)
    assert r.status_code == 200, r.text
    return _latest_entry(client, headers, "project_deleted", project_id)


def _project_ids(
    client: TestClient, headers: dict[str, str], **params: object
) -> set[str]:
    r = client.get(f"{API}/projects/", headers=headers, params=params)
    return {project["id"] for project in r.json()["data"]}


def test_restoring_a_project_brings_it_back_with_its_tasks(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    r = client.post(
        f"{API}/projects/",
        headers=headers,
        json={"name": "Garden", "description": "Back yard"},
    )
    project = r.json()
    root = _create_task(client, headers, "Plant beds", project_id=project["id"])
    _create_task(client, headers, "Buy soil", parent_id=root["id"])
    _create_task(client, headers, "Fix the fence", project_id=project["id"])
    entry = _delete_project(client, headers, project["id"])
    assert entry["restorable"] is True
    assert project["id"] not in _project_ids(client, headers)

    r = _restore(client, headers, entry)
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/projects/", headers=headers)
    [restored] = [p for p in r.json()["data"] if p["id"] == project["id"]]
    assert restored == project
    assert _visible_titles(client, headers) == {
        "Plant beds",
        "Buy soil",
        "Fix the fence",
    }


def test_a_task_deleted_on_its_own_before_its_project_stays_deleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Garden")
    _create_task(client, headers, "Plant beds", project_id=project["id"])
    dropped = _create_task(client, headers, "Build a pond", project_id=project["id"])

    # The task goes first, on its own; then the project.
    dropped_entry = _delete_task(client, headers, dropped["id"])
    project_entry = _delete_project(client, headers, project["id"])

    assert _restore(client, headers, project_entry).status_code == 200
    assert _visible_titles(client, headers) == {"Plant beds"}

    # Its own deletion still brings it back, into the restored project.
    assert _restore(client, headers, dropped_entry).status_code == 200
    assert _visible_titles(client, headers) == {"Plant beds", "Build a pond"}


def test_a_project_archived_when_deleted_comes_back_archived(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Someday")
    _create_task(client, headers, "Learn the cello", project_id=project["id"])
    r = client.post(f"{API}/projects/{project['id']}/archive", headers=headers)
    assert r.status_code == 200
    entry = _delete_project(client, headers, project["id"])

    r = _restore(client, headers, entry)
    assert r.status_code == 200, r.text

    assert project["id"] not in _project_ids(client, headers)
    assert project["id"] in _project_ids(client, headers, archived=True)
    r = client.get(f"{API}/tasks/", headers=headers, params={"archived": True})
    assert [t["title"] for t in r.json()["data"]] == ["Learn the cello"]


def test_a_project_restore_that_would_reopen_a_series_is_refused_whole(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    inbox = next(
        p["id"]
        for p in client.get(f"{API}/projects/", headers=headers).json()["data"]
        if p["is_inbox"]
    )
    first = _create_task(
        client,
        headers,
        "Water plants",
        project_id=project["id"],
        due_date="2026-03-02",
        recurrence={"frequency": "weekly"},
    )
    _create_task(client, headers, "Fix the tap", project_id=project["id"])
    r = client.patch(
        f"{API}/tasks/{first['id']}", headers=headers, json={"completed": True}
    )
    assert r.status_code == 200
    # The completed occurrence leaves the project; its successor stays in it.
    r = client.patch(
        f"{API}/tasks/{first['id']}", headers=headers, json={"project_id": inbox}
    )
    assert r.status_code == 200
    entry = _delete_project(client, headers, project["id"])
    # With the successor deleted, the first occurrence is the latest left and
    # can be reopened, so the series is open again outside the project.
    r = client.patch(
        f"{API}/tasks/{first['id']}", headers=headers, json={"completed": False}
    )
    assert r.status_code == 200, r.text

    r = _restore(client, headers, entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "series_has_open_occurrence"

    assert project["id"] not in _project_ids(client, headers)
    assert _visible_titles(client, headers) == {"Water plants"}


def test_restoring_a_project_twice_changes_nothing_the_second_time(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Garden")
    _create_task(client, headers, "Plant beds", project_id=project["id"])
    entry = _delete_project(client, headers, project["id"])
    assert _restore(client, headers, entry).status_code == 200
    log_length = client.get(f"{API}/activity-log/", headers=headers).json()["count"]

    r = _restore(client, headers, entry)
    assert r.status_code == 200
    assert project["id"] in _project_ids(client, headers)
    assert (
        client.get(f"{API}/activity-log/", headers=headers).json()["count"]
        == log_length
    )


def test_restoring_a_project_deleted_again_since_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Garden")
    first_entry = _delete_project(client, headers, project["id"])
    assert _restore(client, headers, first_entry).status_code == 200
    second_entry = _delete_project(client, headers, project["id"])

    r = _restore(client, headers, first_entry)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "deleted_again"

    assert _restore(client, headers, second_entry).status_code == 200


def test_a_project_restore_is_logged_once_for_the_project(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Garden")
    root = _create_task(client, headers, "Plant beds", project_id=project["id"])
    _create_task(client, headers, "Buy soil", parent_id=root["id"])
    entry = _delete_project(client, headers, project["id"])

    assert _restore(client, headers, entry).status_code == 200

    restored = _latest_entry(client, headers, "project_restored", project["id"])
    assert restored["deletion_id"] == entry["deletion_id"]
    assert restored["details"] == {"name": "Garden", "task_count": 2}

    deleted = _latest_entry(client, headers, "project_deleted", project["id"])
    assert deleted["details"] == entry["details"]
    assert deleted["restorable"] is False

    actions = [
        e["action"]
        for e in client.get(f"{API}/activity-log/", headers=headers).json()["data"]
    ]
    assert "task_restored" not in actions
    assert actions.count("project_restored") == 1
