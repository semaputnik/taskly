"""
Reading one project's history: the log narrowed to a single project.

The project panel's Activity section is the project's own chronology, so the
log has to answer "what happened here" without the client reading the whole
account's log. The narrowing never widens the log: it is the caller's own
entries, filtered (FR-10.7), and a project that is not the caller's is refused
rather than read as an empty history.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    create_project,
    create_task,
    create_user_headers,
    delete_task,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _history(client: TestClient, headers: Headers, project_id: str) -> Any:
    r = client.get(
        f"{API}/activity-log/", headers=headers, params={"project_id": project_id}
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_the_filter_returns_what_happened_in_the_project(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Website")
    elsewhere = create_project(client, owner, "Home")
    task_id = create_task(client, owner, project_id=project_id, title="Banner")
    create_task(client, owner, project_id=elsewhere, title="Not this one")
    client.post(
        f"{API}/tasks/{task_id}/comments/", headers=owner, json={"body": "Hello"}
    )
    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"priority": "P1"})

    page = _history(client, owner, project_id)

    assert [entry["action"] for entry in page["data"]] == [
        "task_changed",
        "comment_added",
        "task_created",
        "project_created",
    ]
    assert page["count"] == 4


def test_a_deleted_task_is_still_in_the_project_it_was_deleted_from(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Website")
    task_id = create_task(client, owner, project_id=project_id)
    delete_task(client, owner, task_id)

    page = _history(client, owner, project_id)

    assert page["data"][0]["action"] == "task_deleted"


def test_a_project_that_is_not_the_callers_is_not_found(
    client: TestClient, owner: Headers, db: Session
) -> None:
    other = create_user_headers(client, db)
    theirs = create_project(client, other, "Theirs")

    for project_id in (theirs, str(uuid.uuid4())):
        r = client.get(
            f"{API}/activity-log/", headers=owner, params={"project_id": project_id}
        )
        assert r.status_code == 404
