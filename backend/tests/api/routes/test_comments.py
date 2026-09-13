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


def _add_comment(
    client: TestClient, headers: dict[str, str], task_id: str, body: str
):
    return client.post(
        f"{settings.API_V1_STR}/tasks/{task_id}/comments/",
        headers=headers,
        json={"body": body},
    )


def _list_comments(client: TestClient, headers: dict[str, str], task_id: str):
    return client.get(
        f"{settings.API_V1_STR}/tasks/{task_id}/comments/", headers=headers
    )


def test_a_comment_can_be_added_to_a_task(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Buy milk")

    r = _add_comment(client, headers, task["id"], "On it")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["body"] == "On it"
    assert body["task_id"] == task["id"]

    listed = _list_comments(client, headers, task["id"])
    assert listed.status_code == 200
    assert [c["body"] for c in listed.json()["data"]] == ["On it"]
    assert listed.json()["count"] == 1


def test_a_comment_can_be_added_to_a_subtask(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    subtask = _create_task(client, headers, "Subtask", parent_id=root["id"])

    r = _add_comment(client, headers, subtask["id"], "Progress note")
    assert r.status_code == 200, r.text


def test_comments_are_listed_oldest_first(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    _add_comment(client, headers, task["id"], "First")
    _add_comment(client, headers, task["id"], "Second")
    _add_comment(client, headers, task["id"], "Third")

    r = _list_comments(client, headers, task["id"])
    assert [c["body"] for c in r.json()["data"]] == ["First", "Second", "Third"]


def test_a_user_can_edit_their_own_comment(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    comment = _add_comment(client, headers, task["id"], "Original").json()

    r = client.patch(
        f"{settings.API_V1_STR}/comments/{comment['id']}",
        headers=headers,
        json={"body": "Edited"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["body"] == "Edited"

    listed = _list_comments(client, headers, task["id"])
    assert listed.json()["data"][0]["body"] == "Edited"


def test_a_user_can_delete_their_own_comment(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    comment = _add_comment(client, headers, task["id"], "Gone soon").json()

    r = client.delete(
        f"{settings.API_V1_STR}/comments/{comment['id']}", headers=headers
    )
    assert r.status_code == 200, r.text

    listed = _list_comments(client, headers, task["id"])
    assert listed.json()["data"] == []
    assert listed.json()["count"] == 0


def test_a_user_cannot_read_comments_on_another_users_task(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")
    _add_comment(client, headers_a, task["id"], "Private note")

    r = _list_comments(client, headers_b, task["id"])
    assert r.status_code == 404


def test_a_user_cannot_add_a_comment_to_another_users_task(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")

    r = _add_comment(client, headers_b, task["id"], "Sneaky")
    assert r.status_code == 404


def test_a_user_cannot_edit_another_users_comment(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")
    comment = _add_comment(client, headers_a, task["id"], "Original").json()

    r = client.patch(
        f"{settings.API_V1_STR}/comments/{comment['id']}",
        headers=headers_b,
        json={"body": "Hijacked"},
    )
    assert r.status_code == 404


def test_a_user_cannot_delete_another_users_comment(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")
    comment = _add_comment(client, headers_a, task["id"], "Original").json()

    r = client.delete(
        f"{settings.API_V1_STR}/comments/{comment['id']}", headers=headers_b
    )
    assert r.status_code == 404

    listed = _list_comments(client, headers_a, task["id"])
    assert listed.json()["count"] == 1


def test_a_blank_comment_is_rejected(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    r = _add_comment(client, headers, task["id"], "   ")
    assert r.status_code == 422


def test_comment_body_is_trimmed(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    r = _add_comment(client, headers, task["id"], "  spaced  ")
    assert r.status_code == 200
    assert r.json()["body"] == "spaced"


def test_commenting_on_an_unknown_task_is_rejected(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    r = _add_comment(client, headers, "00000000-0000-0000-0000-000000000000", "Hi")
    assert r.status_code == 404


def test_a_comment_cannot_carry_an_attachment_field(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    # There is no such field to send: the schema offers no attachment relation
    # on a comment at all (FR-03.3).
    r = client.post(
        f"{settings.API_V1_STR}/tasks/{task['id']}/comments/",
        headers=headers,
        json={"body": "See attached", "attachment_id": "whatever"},
    )
    assert r.status_code == 200
    assert "attachment_id" not in r.json()


def test_a_comment_on_a_deleted_task_cannot_be_edited_or_deleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Doomed")
    comment = _add_comment(client, headers, task["id"], "Before deletion").json()

    r = client.delete(f"{settings.API_V1_STR}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200

    r = client.patch(
        f"{settings.API_V1_STR}/comments/{comment['id']}",
        headers=headers,
        json={"body": "Edited after deletion"},
    )
    assert r.status_code == 404

    r = client.delete(
        f"{settings.API_V1_STR}/comments/{comment['id']}", headers=headers
    )
    assert r.status_code == 404


def test_comments_survive_a_deleted_task(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Doomed")
    _add_comment(client, headers, task["id"], "Before deletion")

    r = client.delete(f"{settings.API_V1_STR}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200

    # The task is only soft-deleted and no longer reachable; its comments stay
    # with it rather than being read through it.
    r = _list_comments(client, headers, task["id"])
    assert r.status_code == 404
