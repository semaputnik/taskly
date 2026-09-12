from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import crud
from app.core.config import settings
from app.models import Tag, UserCreate
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


def _create_project(client: TestClient, headers: dict[str, str], name: str) -> str:
    r = client.post(
        f"{settings.API_V1_STR}/projects/", headers=headers, json={"name": name}
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


def _set_tags(
    client: TestClient, headers: dict[str, str], task_id: str, tags: list[str]
):
    return client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}", headers=headers, json={"tags": tags}
    )


def _listed_tags(client: TestClient, headers: dict[str, str], **query: object):
    r = client.get(f"{settings.API_V1_STR}/tags/", headers=headers, params=query)
    assert r.status_code == 200, r.text
    return [tag["name"] for tag in r.json()["data"]]


def _stored_tag_count(db: Session, name: str) -> int:
    db.expire_all()
    return db.exec(select(func.count()).select_from(Tag).where(Tag.name == name)).one()


def test_a_tag_is_created_by_typing_it_onto_a_task(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    task = _create_task(client, headers, "Buy milk", tags=["errands"])
    assert task["tags"] == ["errands"]
    assert _listed_tags(client, headers) == ["errands"]


def test_applying_an_existing_tag_reuses_it(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    name = random_lower_string()

    first = _create_task(client, headers, "First", tags=[name])
    second = _create_task(client, headers, "Second", tags=[name])

    assert first["tags"] == [name]
    assert second["tags"] == [name]
    assert _listed_tags(client, headers) == [name]
    assert _stored_tag_count(db, name) == 1


def test_two_users_can_use_the_same_tag_name(client: TestClient, db: Session) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    name = random_lower_string()

    _create_task(client, headers_a, "A's task", tags=[name])
    _create_task(client, headers_b, "B's task", tags=[name])

    assert _listed_tags(client, headers_a) == [name]
    assert _listed_tags(client, headers_b) == [name]
    # One row each: the name is unique per user, not globally.
    assert _stored_tag_count(db, name) == 2


def test_a_users_tags_do_not_leak_to_another_user(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)

    _create_task(client, headers_a, "A's task", tags=["private"])

    assert _listed_tags(client, headers_b) == []


def test_a_tag_crosses_projects(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    work_id = _create_project(client, headers, "Work")
    home_id = _create_project(client, headers, "Home")

    _create_task(client, headers, "At work", project_id=work_id, tags=["urgent"])
    # The tag is offered everywhere, and applying it in another project reuses it.
    assert _listed_tags(client, headers) == ["urgent"]
    other = _create_task(
        client, headers, "At home", project_id=home_id, tags=["urgent"]
    )

    assert other["tags"] == ["urgent"]
    assert _stored_tag_count(db, "urgent") == 1


def test_removing_a_tag_leaves_other_tasks_alone(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    name = random_lower_string()
    kept = _create_task(client, headers, "Kept", tags=[name])
    stripped = _create_task(client, headers, "Stripped", tags=[name, "other"])

    r = _set_tags(client, headers, stripped["id"], ["other"])
    assert r.status_code == 200
    assert r.json()["tags"] == ["other"]

    r = client.get(f"{settings.API_V1_STR}/tasks/{kept['id']}", headers=headers)
    assert r.json()["tags"] == [name]
    assert _stored_tag_count(db, name) == 1


def test_a_tag_left_on_no_task_stops_being_offered(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    name = random_lower_string()
    task = _create_task(client, headers, "Only task", tags=[name])

    _set_tags(client, headers, task["id"], [])

    # There is no tag-management screen, so a tag nothing carries any more has
    # to drop out of autocomplete by itself.
    assert _listed_tags(client, headers) == []
    assert _stored_tag_count(db, name) == 0


def test_tags_survive_a_deleted_task(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    name = random_lower_string()
    task = _create_task(client, headers, "Doomed", tags=[name])

    r = client.delete(f"{settings.API_V1_STR}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200

    # The task is only soft-deleted: its tags have to be there when it comes back.
    assert _stored_tag_count(db, name) == 1


def test_tags_can_be_replaced_wholesale(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task", tags=["one", "two"])

    r = _set_tags(client, headers, task["id"], ["two", "three"])
    assert r.status_code == 200
    assert r.json()["tags"] == ["three", "two"]


def test_omitting_tags_leaves_them_untouched(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task", tags=["keep"])

    r = client.patch(
        f"{settings.API_V1_STR}/tasks/{task['id']}",
        headers=headers,
        json={"title": "Renamed"},
    )
    assert r.status_code == 200
    assert r.json()["tags"] == ["keep"]


def test_tags_are_reported_in_a_stable_order_without_duplicates(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    task = _create_task(client, headers, "Task", tags=["beta", "alpha", "beta"])
    assert task["tags"] == ["alpha", "beta"]

    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers)
    assert r.json()["data"][0]["tags"] == ["alpha", "beta"]


def test_tag_names_are_trimmed(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    task = _create_task(client, headers, "Task", tags=["  spaced  "])
    assert task["tags"] == ["spaced"]


def test_a_blank_tag_is_rejected(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Task", "tags": ["   "]},
    )
    assert r.status_code == 422


def test_an_overlong_tag_is_rejected(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": "Task", "tags": ["x" * 51]},
    )
    assert r.status_code == 422


def test_a_subtask_carries_tags_like_any_other_task(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root", tags=["shared"])

    subtask = _create_task(
        client, headers, "Subtask", parent_id=root["id"], tags=["shared", "own"]
    )
    assert subtask["tags"] == ["own", "shared"]
    assert _stored_tag_count(db, "shared") == 1


def test_tags_can_be_filtered_for_autocomplete(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    _create_task(client, headers, "Task", tags=["Reading", "running", "errands"])

    assert _listed_tags(client, headers) == ["errands", "Reading", "running"]
    # Matching ignores case, so what the user types finds what they typed before.
    assert _listed_tags(client, headers, q="R") == ["Reading", "running"]
    assert _listed_tags(client, headers, q="read") == ["Reading"]


def test_tags_of_another_users_task_cannot_be_set(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")

    r = _set_tags(client, headers_b, task["id"], ["hijacked"])
    assert r.status_code == 404
