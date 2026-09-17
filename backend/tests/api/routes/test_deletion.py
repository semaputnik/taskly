import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Deletion, Project, Task, UserCreate
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
    assert r.status_code == 200, r.text
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


def _listed_titles(client: TestClient, headers: dict[str, str]) -> set[str]:
    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers)
    assert r.status_code == 200, r.text
    return {t["title"] for t in r.json()["data"]}


def _delete_task(
    client: TestClient, headers: dict[str, str], task_id: str, **params: object
):
    return client.delete(
        f"{settings.API_V1_STR}/tasks/{task_id}", headers=headers, params=params
    )


def _stored_task(db: Session, task_id: str) -> Task:
    """The row as the database holds it, deleted or not."""
    db.expire_all()
    task = db.get(Task, uuid.UUID(task_id))
    assert task is not None, "the row should survive a deletion"
    return task


def _stored_project(db: Session, project_id: str) -> Project:
    db.expire_all()
    project = db.get(Project, uuid.UUID(project_id))
    assert project is not None, "the row should survive a deletion"
    return project


def test_deleting_a_task_hides_it_but_keeps_the_row(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Throwaway")

    r = _delete_task(client, headers, task["id"])
    assert r.status_code == 200

    assert _listed_titles(client, headers) == set()
    r = client.get(f"{settings.API_V1_STR}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 404

    stored = _stored_task(db, task["id"])
    assert stored.title == "Throwaway"
    assert stored.deletion_id is not None


def test_deleting_a_task_with_subtasks_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])

    r = _delete_task(client, headers, root["id"])
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "task_has_subtasks"

    assert _listed_titles(client, headers) == {"Root", "Child"}
    assert _stored_task(db, root["id"]).deletion_id is None
    assert _stored_task(db, child["id"]).deletion_id is None


def test_deleting_a_task_with_subtasks_cascades_when_confirmed(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])
    bystander = _create_task(client, headers, "Bystander")

    r = _delete_task(client, headers, root["id"], delete_subtasks=True)
    assert r.status_code == 200

    assert _listed_titles(client, headers) == {"Bystander"}
    for task_id in (root["id"], child["id"], grandchild["id"]):
        assert _stored_task(db, task_id).deletion_id is not None
    assert _stored_task(db, bystander["id"]).deletion_id is None


def test_a_whole_cascade_shares_one_deletion_event(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Grandchild", parent_id=child["id"])

    _delete_task(client, headers, root["id"], delete_subtasks=True)

    deletion_ids = {
        _stored_task(db, task["id"]).deletion_id for task in (root, child, grandchild)
    }
    assert len(deletion_ids) == 1

    deletion = db.get(Deletion, deletion_ids.pop())
    assert deletion is not None
    # The event names what the user pointed at, not what went down with it.
    assert deletion.task_id == uuid.UUID(root["id"])
    assert deletion.project_id is None


def test_a_subtask_deleted_on_its_own_stays_distinguishable(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    early = _create_task(client, headers, "Deleted early", parent_id=root["id"])
    sibling = _create_task(client, headers, "Sibling", parent_id=root["id"])

    _delete_task(client, headers, early["id"])
    early_deletion_id = _stored_task(db, early["id"]).deletion_id

    _delete_task(client, headers, root["id"], delete_subtasks=True)

    root_deletion_id = _stored_task(db, root["id"]).deletion_id
    assert _stored_task(db, sibling["id"]).deletion_id == root_deletion_id
    # Its own deletion is untouched, so a later restore of the root leaves it out.
    assert _stored_task(db, early["id"]).deletion_id == early_deletion_id
    assert early_deletion_id != root_deletion_id


def test_a_task_whose_subtasks_are_all_deleted_needs_no_confirmation(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])

    _delete_task(client, headers, child["id"])

    r = _delete_task(client, headers, root["id"])
    assert r.status_code == 200


def test_deleting_a_project_deletes_its_tasks(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Work")

    root = _create_task(client, headers, "Root", project_id=project_id)
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    elsewhere = _create_task(client, headers, "In the Inbox")

    r = client.delete(f"{settings.API_V1_STR}/projects/{project_id}", headers=headers)
    assert r.status_code == 200

    assert _listed_titles(client, headers) == {"In the Inbox"}
    r = client.get(f"{settings.API_V1_STR}/projects/", headers=headers)
    assert "Work" not in {p["name"] for p in r.json()["data"]}

    stored_project = _stored_project(db, project_id)
    assert stored_project.deletion_id is not None
    for task in (root, child):
        assert _stored_task(db, task["id"]).deletion_id == stored_project.deletion_id
    assert _stored_task(db, elsewhere["id"]).deletion_id is None

    deletion = db.get(Deletion, stored_project.deletion_id)
    assert deletion is not None
    assert deletion.project_id == uuid.UUID(project_id)
    assert deletion.task_id is None


def test_deleting_a_project_leaves_a_task_deleted_earlier_alone(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Work")
    early = _create_task(client, headers, "Deleted early", project_id=project_id)
    other = _create_task(client, headers, "Still there", project_id=project_id)

    _delete_task(client, headers, early["id"])
    early_deletion_id = _stored_task(db, early["id"]).deletion_id

    client.delete(f"{settings.API_V1_STR}/projects/{project_id}", headers=headers)

    assert _stored_task(db, early["id"]).deletion_id == early_deletion_id
    assert _stored_task(db, other["id"]).deletion_id != early_deletion_id


def test_a_deleted_subtask_does_not_block_completing_its_parent(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])

    _delete_task(client, headers, child["id"])

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{root['id']}",
        headers=headers,
        json={"status": "done"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_a_deleted_task_cannot_be_used_as_a_parent(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Gone")
    _delete_task(client, headers, task["id"])

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Orphan", "parent_id": task["id"]},
    )
    assert r.status_code == 404


def test_a_deleted_project_cannot_take_new_tasks(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Work")
    client.delete(f"{settings.API_V1_STR}/projects/{project_id}", headers=headers)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Homeless", "project_id": project_id},
    )
    assert r.status_code == 404

    task = _create_task(client, headers, "Somewhere else")
    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task['id']}",
        headers=headers,
        json={"project_id": project_id},
    )
    assert r.status_code == 404


def test_deleting_a_task_twice_returns_404(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Throwaway")

    assert _delete_task(client, headers, task["id"]).status_code == 200
    assert _delete_task(client, headers, task["id"]).status_code == 404


def test_users_cannot_delete_each_others_tasks(client: TestClient, db: Session) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")

    assert _delete_task(client, headers_b, task["id"]).status_code == 404
    assert _stored_task(db, task["id"]).deletion_id is None


def test_deleting_a_nonexistent_task_returns_404(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    r = _delete_task(client, headers, str(uuid.uuid4()))
    assert r.status_code == 404


def test_deleting_the_inbox_is_still_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    inbox_id = _inbox_id(client, headers)

    r = client.delete(f"{settings.API_V1_STR}/projects/{inbox_id}", headers=headers)
    assert r.status_code == 400
    assert _stored_project(db, inbox_id).deletion_id is None
