"""
Reading one record by its id: what a record's panel is addressed by.

A panel fetches the record it names rather than reading it out of the list
behind it, so a link opens a record the current filter excludes. The projects
list carries the number of tasks resolving to each project for the same
reason the tags list carries its own count: archiving and deleting both need
it (FR-05.9, FR-05.11, FR-01.26).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    READ_ONLY,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
    error_code,
    issue_bot_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _project(client: TestClient, headers: Headers, project_id: str) -> Any:
    return client.get(f"{API}/projects/{project_id}", headers=headers)


def _tag(client: TestClient, headers: Headers, tag_id: str) -> Any:
    return client.get(f"{API}/tags/{tag_id}", headers=headers)


def _bot(client: TestClient, headers: Headers, bot_user_id: str) -> Any:
    return client.get(f"{API}/bot-users/{bot_user_id}", headers=headers)


def _create_tag(client: TestClient, headers: Headers, name: str) -> Any:
    r = client.post(f"{API}/tags/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


# --- One record, by its id -----------------------------------------------------


def test_a_project_is_read_by_its_id(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner, "Kitchen rebuild")

    r = _project(client, owner, project_id)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Kitchen rebuild"
    assert r.json()["is_inbox"] is False


def test_a_tag_is_read_by_its_id(client: TestClient, owner: Headers) -> None:
    tag = _create_tag(client, owner, "errands")

    r = _tag(client, owner, tag["id"])
    assert r.status_code == 200, r.text
    assert r.json() == {**tag, "task_count": 0}


def test_a_bot_user_is_read_by_its_id(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=READ_ONLY
    )

    r = _bot(client, owner, bot["id"])
    assert r.status_code == 200, r.text
    assert r.json() == bot
    assert r.json()["deleted"] is False


def test_an_archived_project_is_still_read_by_its_id(
    client: TestClient, owner: Headers
) -> None:
    """The panel is where unarchiving happens, so it has to open."""
    project_id = create_project(client, owner, "Old house")
    assert (
        client.post(f"{API}/projects/{project_id}/archive", headers=owner).status_code
        == 200
    )

    r = _project(client, owner, project_id)
    assert r.status_code == 200, r.text
    assert r.json()["is_archived"] is True


# --- Whose record it is --------------------------------------------------------


def test_another_users_records_are_not_found(
    client: TestClient, db: Session, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    tag = _create_tag(client, owner, "mine")
    bot = create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)

    other = create_user_headers(client, db)
    assert _project(client, other, project_id).status_code == 404
    assert _tag(client, other, tag["id"]).status_code == 404
    assert _bot(client, other, bot["id"]).status_code == 404


def test_a_deleted_record_is_not_found(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner, "Gone")
    tag = _create_tag(client, owner, "gone")

    assert client.delete(f"{API}/projects/{project_id}", headers=owner).status_code
    assert client.delete(f"{API}/tags/{tag['id']}", headers=owner).status_code == 200

    assert _project(client, owner, project_id).status_code == 404
    assert _tag(client, owner, tag["id"]).status_code == 404


def test_a_deleted_bot_user_is_still_read_by_its_id(
    client: TestClient, owner: Headers
) -> None:
    """
    A bot user is kept rather than removed so that what it did still names it
    (FR-08.19), so its panel has to open and say what it now is.
    """
    bot = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY, name="Retired agent"
    )
    assert (
        client.delete(f"{API}/bot-users/{bot['id']}", headers=owner).status_code == 200
    )

    r = _bot(client, owner, bot["id"])
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Retired agent"
    assert r.json()["deleted"] is True

    # It is gone from the list, and takes nothing new.
    listed = client.get(f"{API}/bot-users/", headers=owner).json()["data"]
    assert bot["id"] not in [row["id"] for row in listed]
    assert (
        client.patch(
            f"{API}/bot-users/{bot['id']}", headers=owner, json={"name": "Back"}
        ).status_code
        == 404
    )
    assert (
        client.post(f"{API}/bot-users/{bot['id']}/token", headers=owner).status_code
        == 404
    )
    assert (
        client.delete(f"{API}/bot-users/{bot['id']}", headers=owner).status_code == 404
    )


# --- What a bot user may read --------------------------------------------------


def test_a_bot_reads_a_project_in_its_scope_and_no_other(
    client: TestClient, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Out of scope")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=READ_ONLY
    )

    assert _project(client, bot, in_scope).json()["name"] == "In scope"
    r = _project(client, bot, out_of_scope)
    assert r.status_code == 403
    assert error_code(r) == "outside_scope"


def test_a_bot_never_reads_an_archived_project(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Shelved")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    client.post(f"{API}/projects/{project_id}/archive", headers=owner)

    r = _project(client, bot, project_id)
    assert r.status_code == 403
    assert error_code(r) == "project_archived"


def test_a_bot_reads_a_tag_whatever_its_scope(
    client: TestClient, owner: Headers
) -> None:
    """Tags belong to the user, so no scope narrows them (ADR-0003)."""
    tag = _create_tag(client, owner, "errands")
    bot = issue_bot_headers(client, owner, project_ids=[], permissions={})

    r = _tag(client, bot, tag["id"])
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "errands"


def test_a_bot_never_reads_a_bot_user(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    r = _bot(client, bot, bot_user["id"])
    assert r.status_code == 403
    assert error_code(r) == "human_only"


# --- What a project holds ------------------------------------------------------


def test_a_project_reports_the_tasks_that_resolve_to_it(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Move house")
    root = create_task(client, owner, project_id=project_id, title="Pack the study")
    # A subtask holds no project of its own but resolves to its root's, so it
    # counts where its tree does (FR-02.4).
    create_task(client, owner, parent_id=root, title="Empty the drawers")
    elsewhere = create_project(client, owner, "Untouched")

    counts = {
        project["id"]: project["task_count"]
        for project in client.get(f"{API}/projects/", headers=owner).json()["data"]
    }
    assert counts[project_id] == 2
    assert counts[elsewhere] == 0
    assert _project(client, owner, project_id).json()["task_count"] == 2


def test_a_deleted_task_is_not_counted(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    create_task(client, owner, project_id=project_id, title="Stays")

    assert client.delete(f"{API}/tasks/{task_id}", headers=owner).status_code == 200

    assert _project(client, owner, project_id).json()["task_count"] == 1


def test_the_inbox_counts_the_tasks_that_landed_in_it(
    client: TestClient, owner: Headers
) -> None:
    create_task(client, owner, title="No project of its own")

    projects = client.get(f"{API}/projects/", headers=owner).json()["data"]
    inbox = next(project for project in projects if project["is_inbox"])
    assert inbox["task_count"] == 1


def test_every_project_response_reports_what_it_holds(
    client: TestClient, owner: Headers
) -> None:
    """
    A client that reads the answer instead of asking again must not be told
    the project it just renamed is empty.
    """
    project_id = create_project(client, owner, "Move house")
    create_task(client, owner, project_id=project_id)

    renamed = client.patch(
        f"{API}/projects/{project_id}", headers=owner, json={"name": "Moving"}
    )
    assert renamed.json()["task_count"] == 1
    archived = client.post(f"{API}/projects/{project_id}/archive", headers=owner)
    assert archived.json()["task_count"] == 1
    live = client.post(f"{API}/projects/{project_id}/unarchive", headers=owner)
    assert live.json()["task_count"] == 1


def test_a_bot_resolves_a_project_it_may_only_write_into(
    client: TestClient, owner: Headers
) -> None:
    """
    Reading a project is not reading its tasks: a write-only integration has
    to be able to resolve the project it is allowed to write into.
    """
    project_id = create_project(client, owner, "Support queue")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions={"create_tasks": True}
    )

    listed = client.get(f"{API}/projects/", headers=bot).json()["data"]
    assert [project["name"] for project in listed] == ["Support queue"]

    r = _project(client, bot, project_id)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Support queue"
