"""
Tags as a bot user reaches them: read whatever its scope, created under a
permission of its own, never renamed or deleted (FR-08.9, ADR-0003).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
    error_code,
    issue_bot_headers,
    token_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]

# Everything but the tags: what a bot user had before tags were grantable.
NO_TAGS = {name: True for name in ALL_PERMISSIONS if name != "create_tags"}


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _tags(client: TestClient, headers: Headers) -> dict[str, dict[str, Any]]:
    r = client.get(f"{API}/tags/", headers=headers)
    assert r.status_code == 200, r.text
    return {tag["name"]: tag for tag in r.json()["data"]}


def _task_tags(client: TestClient, headers: Headers, task_id: str) -> list[str]:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    tags: list[str] = r.json()["tags"]
    return tags


def _tag_task(
    client: TestClient, headers: Headers, task_id: str, tags: list[str]
) -> Any:
    return client.patch(f"{API}/tasks/{task_id}", headers=headers, json={"tags": tags})


def _log(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = client.get(
        f"{API}/activity-log/", headers=headers
    ).json()["data"]
    return entries


# --- The permission -----------------------------------------------------------


def test_creating_tags_is_a_permission_of_its_own_off_by_default(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions={"update_tasks": True}
    )
    assert bot["scope"]["permissions"]["create_tags"] is False

    r = client.patch(
        f"{API}/bot-users/{bot['id']}",
        headers=owner,
        json={
            "scope": {
                "project_ids": [project_id],
                "permissions": {"update_tasks": True, "create_tags": True},
            }
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["scope"]["permissions"]["create_tags"] is True


# --- Applying tags to tasks ---------------------------------------------------


def test_a_bot_applies_and_removes_tags_it_does_not_have_to_create(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    client.post(f"{API}/tags/", headers=owner, json={"name": "home"})
    task_id = create_task(client, owner, project_id=project_id)
    # No permission to create tags: applying what the owner already has needs
    # none.
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=NO_TAGS
    )

    assert _tag_task(client, bot, task_id, ["urgent", "home"]).status_code == 200
    assert _task_tags(client, owner, task_id) == ["home", "urgent"]

    assert _tag_task(client, bot, task_id, ["urgent"]).status_code == 200
    assert _task_tags(client, owner, task_id) == ["urgent"]


def test_a_bot_that_cannot_update_tasks_cannot_tag_one(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    task_id = create_task(client, owner, project_id=project_id)
    bot = issue_bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={"read_tasks": True, "create_tags": True},
    )

    r = _tag_task(client, bot, task_id, ["urgent"])
    assert r.status_code == 403, r.text
    assert error_code(r) == "permission_not_granted"
    assert _task_tags(client, owner, task_id) == []


def test_a_bot_creating_a_task_applies_existing_tags(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=NO_TAGS
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={"title": "Tagged", "project_id": project_id, "tags": ["urgent"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tags"] == ["urgent"]


# --- Names that are not tags yet ----------------------------------------------


def test_a_new_name_is_refused_without_the_permission_and_says_which(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    task_id = create_task(client, owner, project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=NO_TAGS
    )

    r = _tag_task(client, bot, task_id, ["urgent", "backlog", "chores"])
    assert r.status_code == 403, r.text
    assert error_code(r) == "permission_not_granted"
    detail = r.json()["detail"]
    assert detail["permission"] == "create_tags"
    # Only the names that are new, and every one of them.
    assert detail["tags"] == ["backlog", "chores"]
    # Nothing of the request was applied.
    assert _task_tags(client, owner, task_id) == []
    assert set(_tags(client, owner)) == {"urgent"}


def test_a_new_name_on_creation_is_refused_and_creates_no_task(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=NO_TAGS
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={"title": "Tagged", "project_id": project_id, "tags": ["backlog"]},
    )
    assert r.status_code == 403, r.text
    assert error_code(r) == "permission_not_granted"
    assert r.json()["detail"]["tags"] == ["backlog"]
    assert client.get(f"{API}/tasks/", headers=owner).json()["count"] == 0
    assert _tags(client, owner) == {}


def test_a_bot_with_the_permission_creates_tags_by_typing_them_onto_a_task(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={"title": "Tagged", "project_id": project_id, "tags": ["backlog"]},
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]

    assert _tag_task(client, bot, task_id, ["backlog", "chores"]).status_code == 200
    assert _task_tags(client, owner, task_id) == ["backlog", "chores"]
    assert set(_tags(client, owner)) == {"backlog", "chores"}


# --- The tags endpoints -------------------------------------------------------


def test_a_bot_creates_a_tag_through_the_tags_endpoint_only_with_the_permission(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    refused = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=NO_TAGS
    )

    r = client.post(f"{API}/tags/", headers=refused, json={"name": "backlog"})
    assert r.status_code == 403, r.text
    assert error_code(r) == "permission_not_granted"
    assert r.json()["detail"]["permission"] == "create_tags"
    assert _tags(client, owner) == {}

    allowed = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    r = client.post(f"{API}/tags/", headers=allowed, json={"name": "backlog"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "backlog"
    assert set(_tags(client, owner)) == {"backlog"}


def test_a_bot_reads_its_owners_whole_vocabulary_whatever_its_scope(
    client: TestClient, db: Session, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Out of scope")
    client.post(
        f"{API}/tasks/",
        headers=owner,
        json={"title": "Elsewhere", "project_id": out_of_scope, "tags": ["elsewhere"]},
    )
    client.post(f"{API}/tags/", headers=owner, json={"name": "unused"})

    other = create_user_headers(client, db)
    client.post(f"{API}/tags/", headers=other, json={"name": "theirs"})

    # Nothing granted, one project in scope: the tags still come whole
    # (ADR-0003).
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions={"read_tasks": True}
    )

    tags = _tags(client, bot)
    assert set(tags) == {"elsewhere", "unused"}
    # With the number of tasks carrying each, counted outside the scope too.
    assert tags["elsewhere"]["task_count"] == 1
    assert tags["unused"]["task_count"] == 0


def test_a_bot_never_renames_or_deletes_a_tag(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    tag = client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"}).json()
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    for r in (
        client.patch(f"{API}/tags/{tag['id']}", headers=bot, json={"name": "renamed"}),
        client.delete(f"{API}/tags/{tag['id']}", headers=bot),
    ):
        assert r.status_code == 403, r.text
        assert error_code(r) == "human_only"
    assert set(_tags(client, owner)) == {"urgent"}


# --- The archive --------------------------------------------------------------


def test_tagging_a_task_in_an_archived_project_is_refused(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    client.post(f"{API}/tags/", headers=owner, json={"name": "urgent"})
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    r = client.post(f"{API}/projects/{project_id}/archive", headers=owner)
    assert r.status_code == 200, r.text

    r = _tag_task(client, bot, task_id, ["urgent"])
    assert r.status_code == 403, r.text
    assert error_code(r) == "project_archived"
    assert _task_tags(client, owner, task_id) == []


# --- Attribution --------------------------------------------------------------


def test_a_tag_a_bot_creates_is_logged_as_the_bots(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Triage bot",
    )
    bot = token_headers(client, owner, bot_user["id"])

    assert (
        client.post(f"{API}/tags/", headers=bot, json={"name": "backlog"}).status_code
        == 200
    )
    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={"title": "Tagged", "project_id": project_id, "tags": ["chores"]},
    )
    assert r.status_code == 200, r.text

    created = [e for e in _log(client, owner) if e["action"] == "tag_created"]
    assert {e["details"]["name"] for e in created} == {"backlog", "chores"}
    for entry in created:
        assert entry["actor_bot_user_id"] == bot_user["id"]
        assert entry["actor_bot_user_name"] == "Triage bot"
        assert entry["actor_id"] is None


# --- Who made it -------------------------------------------------------------


def test_a_tag_a_bot_user_created_names_it(client: TestClient, owner: Headers) -> None:
    """
    The owner can tell an agent's vocabulary from their own, by the
    attribution the activity log already keeps (semaputnik/taskly#69).
    """
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot_headers = token_headers(client, owner, bot["id"])
    task_id = create_task(client, owner, project_id=project_id)
    client.post(f"{API}/tags/", headers=bot_headers, json={"name": "by-api"})
    _tag_task(client, bot_headers, task_id, ["by-typing"])
    client.post(f"{API}/tags/", headers=owner, json={"name": "mine"})

    tags = _tags(client, owner)
    expected = {"id": bot["id"], "name": bot["name"], "deleted": False}
    assert tags["by-api"]["created_by_bot_user"] == expected
    assert tags["by-typing"]["created_by_bot_user"] == expected
    assert tags["mine"]["created_by_bot_user"] is None
    one = client.get(f"{API}/tags/{tags['by-api']['id']}", headers=owner).json()
    assert one["created_by_bot_user"] == expected

    # A deleted bot user stays named, marked deleted.
    client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)
    assert _tags(client, owner)["by-api"]["created_by_bot_user"] == {
        **expected,
        "deleted": True,
    }
