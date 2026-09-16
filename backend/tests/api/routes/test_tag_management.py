"""
Tags as the user manages them: created on their own, renamed and deleted
(FR-01.20–FR-01.26, ADR-0003).
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import TaskTag
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_project,
    create_user_headers,
    error_code,
    issue_bot_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _create_tag(client: TestClient, headers: Headers, name: str) -> Any:
    return client.post(f"{API}/tags/", headers=headers, json={"name": name})


def _rename(client: TestClient, headers: Headers, tag_id: str, name: str) -> Any:
    return client.patch(f"{API}/tags/{tag_id}", headers=headers, json={"name": name})


def _delete(client: TestClient, headers: Headers, tag_id: str) -> Any:
    return client.delete(f"{API}/tags/{tag_id}", headers=headers)


def _tags(client: TestClient, headers: Headers) -> dict[str, dict[str, Any]]:
    r = client.get(f"{API}/tags/", headers=headers)
    assert r.status_code == 200, r.text
    return {tag["name"]: tag for tag in r.json()["data"]}


def _task(client: TestClient, headers: Headers, tags: list[str], **fields: Any) -> str:
    r = client.post(
        f"{API}/tasks/", headers=headers, json={"title": "T", "tags": tags, **fields}
    )
    assert r.status_code == 200, r.text
    task_id: str = r.json()["id"]
    return task_id


def _task_tags(client: TestClient, headers: Headers, task_id: str) -> list[str]:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    tags: list[str] = r.json()["tags"]
    return tags


def _log(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    """The user's log, oldest first."""
    entries: list[dict[str, Any]] = client.get(
        f"{API}/activity-log/", headers=headers
    ).json()["data"]
    return list(reversed(entries))


# --- Creating -----------------------------------------------------------------


def test_a_tag_is_created_on_its_own_and_stays_without_tasks(
    client: TestClient, owner: Headers
) -> None:
    r = _create_tag(client, owner, "  errands ")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "errands"
    assert r.json()["task_count"] == 0

    listed = _tags(client, owner)
    assert listed["errands"] == r.json()

    # It can then be put on a task like any other tag.
    task_id = _task(client, owner, ["errands"])
    assert _tags(client, owner)["errands"]["id"] == r.json()["id"]
    assert _tags(client, owner)["errands"]["task_count"] == 1
    assert _task_tags(client, owner, task_id) == ["errands"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_a_tag_needs_a_name_of_up_to_50_characters(
    client: TestClient, owner: Headers, name: str
) -> None:
    assert _create_tag(client, owner, name).status_code == 422
    assert _tags(client, owner) == {}


def test_a_name_already_taken_is_refused_and_names_are_case_sensitive(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["urgent"])

    r = _create_tag(client, owner, "urgent")
    assert r.status_code == 409
    assert error_code(r) == "tag_exists"
    assert _create_tag(client, owner, "Urgent").status_code == 200
    assert set(_tags(client, owner)) == {"urgent", "Urgent"}


def test_the_same_name_is_free_for_another_user(
    client: TestClient, db: Session, owner: Headers
) -> None:
    _create_tag(client, owner, "home")
    other = create_user_headers(client, db)

    assert _create_tag(client, other, "home").status_code == 200
    assert _tags(client, other)["home"]["id"] != _tags(client, owner)["home"]["id"]


# --- Counting -----------------------------------------------------------------


def test_the_task_count_leaves_out_deleted_tasks(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["home"])
    _task(client, owner, ["home", "work"])
    deleted = _task(client, owner, ["home"])
    client.delete(f"{API}/tasks/{deleted}", headers=owner)

    listed = _tags(client, owner)
    assert listed["home"]["task_count"] == 2
    assert listed["work"]["task_count"] == 1


def _archived_project_with_task(
    client: TestClient, headers: Headers, tags: list[str]
) -> str:
    project_id = create_project(client, headers, "Old house")
    root = _task(client, headers, tags, project_id=project_id)
    # A subtask is archived with the project its root task resolves to.
    _task(client, headers, tags, parent_id=root)
    r = client.post(f"{API}/projects/{project_id}/archive", headers=headers)
    assert r.status_code == 200, r.text
    return project_id


def test_the_count_matches_the_task_list_it_links_to(
    client: TestClient, owner: Headers
) -> None:
    # The count is the live tasks — what the list behind it shows — and the
    # tasks archived with their project are reported beside it, not in it.
    _task(client, owner, ["home"])
    project_id = _archived_project_with_task(client, owner, ["home"])

    tag = _tags(client, owner)["home"]
    listed = client.get(f"{API}/tasks/", headers=owner, params={"tag": "home"})
    assert tag["task_count"] == listed.json()["count"] == 1
    assert tag["archived_task_count"] == 2
    one = client.get(f"{API}/tags/{tag['id']}", headers=owner).json()
    assert (one["task_count"], one["archived_task_count"]) == (1, 2)

    # Unarchiving counts them as live again.
    client.post(f"{API}/projects/{project_id}/unarchive", headers=owner)
    tag = _tags(client, owner)["home"]
    listed = client.get(f"{API}/tasks/", headers=owner, params={"tag": "home"})
    assert tag["task_count"] == listed.json()["count"] == 3
    assert tag["archived_task_count"] == 0


def test_a_bot_user_reads_the_same_counts_as_its_owner(
    client: TestClient, owner: Headers
) -> None:
    live_project = create_project(client, owner, "Live")
    _task(client, owner, ["home"], project_id=live_project)
    _task(client, owner, ["home"])
    _archived_project_with_task(client, owner, ["home"])
    bot_headers = issue_bot_headers(
        client, owner, project_ids=[live_project], permissions={"read_tasks": True}
    )

    as_owner = _tags(client, owner)["home"]
    as_bot = _tags(client, bot_headers)["home"]
    assert as_bot == as_owner
    assert (as_bot["task_count"], as_bot["archived_task_count"]) == (2, 2)


def test_deleting_a_tag_takes_it_off_archived_tasks_too(
    client: TestClient, db: Session, owner: Headers
) -> None:
    _archived_project_with_task(client, owner, ["home"])
    tag = _tags(client, owner)["home"]

    assert _delete(client, owner, tag["id"]).status_code == 200

    links = db.exec(select(TaskTag).where(TaskTag.tag_id == uuid.UUID(tag["id"]))).all()
    assert links == []
    archived = client.get(f"{API}/tasks/", headers=owner, params={"archived": True})
    assert [task["tags"] for task in archived.json()["data"]] == [[], []]


# --- Renaming -----------------------------------------------------------------


def test_renaming_a_tag_renames_it_on_every_task(
    client: TestClient, owner: Headers
) -> None:
    first = _task(client, owner, ["chores", "work"])
    second = _task(client, owner, ["chores"])
    tag = _tags(client, owner)["chores"]

    r = _rename(client, owner, tag["id"], "housework")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "id": tag["id"],
        "name": "housework",
        "task_count": 2,
        "archived_task_count": 0,
    }

    assert _task_tags(client, owner, first) == ["housework", "work"]
    assert _task_tags(client, owner, second) == ["housework"]
    r = client.get(f"{API}/tasks/", headers=owner, params={"tag": "housework"})
    assert {t["id"] for t in r.json()["data"]} == {first, second}
    assert "chores" not in _tags(client, owner)


def test_renaming_to_a_taken_name_is_refused(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["home", "house"])
    house = _tags(client, owner)["house"]

    r = _rename(client, owner, house["id"], "home")
    assert r.status_code == 409
    assert error_code(r) == "tag_exists"
    assert set(_tags(client, owner)) == {"home", "house"}


def test_renaming_only_the_case_or_to_the_same_name_works(
    client: TestClient, owner: Headers
) -> None:
    tag = _create_tag(client, owner, "home").json()
    seen = len(_log(client, owner))

    assert _rename(client, owner, tag["id"], "home").status_code == 200
    assert len(_log(client, owner)) == seen
    r = _rename(client, owner, tag["id"], "Home")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Home"


def test_activity_entries_keep_the_name_a_tag_had_then(
    client: TestClient, owner: Headers
) -> None:
    task_id = _task(client, owner, [])
    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"tags": ["chores"]})
    tag = _tags(client, owner)["chores"]

    _rename(client, owner, tag["id"], "housework")

    entries = _log(client, owner)
    changed = next(e for e in entries if e["action"] == "task_changed")
    assert changed["details"]["changes"]["tags"] == {"from": [], "to": ["chores"]}
    renamed = entries[-1]
    assert renamed["action"] == "tag_renamed"
    assert renamed["entity_type"] == "tag"
    assert renamed["entity_id"] == tag["id"]
    assert renamed["details"] == {
        "name": "housework",
        "changes": {"name": {"from": "chores", "to": "housework"}},
    }


# --- Deleting -----------------------------------------------------------------


def test_deleting_a_tag_takes_it_off_every_task(
    client: TestClient, db: Session, owner: Headers
) -> None:
    first = _task(client, owner, ["home", "work"])
    second = _task(client, owner, ["home"])
    tag = _tags(client, owner)["home"]

    r = _delete(client, owner, tag["id"])
    assert r.status_code == 200, r.text

    assert _task_tags(client, owner, first) == ["work"]
    assert _task_tags(client, owner, second) == []
    assert set(_tags(client, owner)) == {"work"}
    links = db.exec(select(TaskTag).where(TaskTag.tag_id == uuid.UUID(tag["id"]))).all()
    assert links == []


def test_a_deleted_tag_does_not_come_back_with_a_restored_task(
    client: TestClient, owner: Headers
) -> None:
    task_id = _task(client, owner, ["home", "work"])
    client.delete(f"{API}/tasks/{task_id}", headers=owner)
    deletion = next(e for e in _log(client, owner) if e["action"] == "task_deleted")

    _delete(client, owner, _tags(client, owner)["home"]["id"])
    r = client.post(f"{API}/activity-log/{deletion['id']}/restore", headers=owner)
    assert r.status_code == 200, r.text

    assert _task_tags(client, owner, task_id) == ["work"]
    assert "home" not in _tags(client, owner)


def test_a_tag_deletion_is_logged_but_cannot_be_restored(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["home"])
    deleted_task = _task(client, owner, ["home"])
    client.delete(f"{API}/tasks/{deleted_task}", headers=owner)
    _task(client, owner, ["home"])
    tag = _tags(client, owner)["home"]

    _delete(client, owner, tag["id"])

    entry = _log(client, owner)[-1]
    assert entry["action"] == "tag_deleted"
    assert entry["entity_id"] == tag["id"]
    assert entry["details"] == {"name": "home", "task_count": 2}
    assert entry["restorable"] is False
    r = client.post(f"{API}/activity-log/{entry['id']}/restore", headers=owner)
    assert r.status_code == 400


def test_a_deleted_tag_name_can_be_used_again_as_a_new_tag(
    client: TestClient, owner: Headers
) -> None:
    old = _create_tag(client, owner, "home").json()
    _delete(client, owner, old["id"])

    r = _create_tag(client, owner, "home")
    assert r.status_code == 200, r.text
    assert r.json()["id"] != old["id"]


# --- Logging ------------------------------------------------------------------


def test_creating_a_tag_either_way_is_logged_once(
    client: TestClient, owner: Headers
) -> None:
    tag = _create_tag(client, owner, "errands").json()
    _task(client, owner, ["errands", "home"])

    entries = [e for e in _log(client, owner) if e["entity_type"] == "tag"]
    assert [(e["action"], e["details"]["name"]) for e in entries] == [
        ("tag_created", "errands"),
        ("tag_created", "home"),
    ]
    assert entries[0]["entity_id"] == tag["id"]


# --- Who may ------------------------------------------------------------------


def test_one_users_tags_cannot_be_renamed_or_deleted_by_another(
    client: TestClient, db: Session, owner: Headers
) -> None:
    tag = _create_tag(client, owner, "home").json()
    other = create_user_headers(client, db)

    assert _rename(client, other, tag["id"], "mine").status_code == 404
    assert _delete(client, other, tag["id"]).status_code == 404
    assert _rename(client, owner, str(uuid.uuid4()), "x").status_code == 404
    assert _tags(client, owner)["home"]["id"] == tag["id"]
    assert _tags(client, other) == {}


def test_a_bot_cannot_rename_or_delete_tags(client: TestClient, owner: Headers) -> None:
    """
    Renaming and deleting change tasks in every project, so no scope could
    allow them (ADR-0003). Creating tags is a bot user's to be granted, and
    lives in `test_bot_tags.py`.
    """
    project_id = create_project(client, owner)
    bot_headers = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    tag = _create_tag(client, owner, "home").json()

    for r in (
        _rename(client, bot_headers, tag["id"], "renamed"),
        _delete(client, bot_headers, tag["id"]),
    ):
        assert r.status_code == 403
        assert error_code(r) == "human_only"
    assert set(_tags(client, owner)) == {"home"}
