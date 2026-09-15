"""
What a bot user can do with comments and attachments (FR-08.10, FR-08.11),
driven over HTTP with its own token.

Each endpoint needs one permission, and the matrix runs every endpoint through
the same four ways a bot is let in or turned away, on a task and a subtask.
"""

from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.api.deps import get_attachment_storage
from app.core.config import settings
from app.main import app
from tests.api.routes.test_attachments import InMemoryAttachmentStorage
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


@pytest.fixture(autouse=True)
def storage() -> Generator[InMemoryAttachmentStorage]:
    fake_storage = InMemoryAttachmentStorage()
    app.dependency_overrides[get_attachment_storage] = lambda: fake_storage
    yield fake_storage
    del app.dependency_overrides[get_attachment_storage]


def _comment(client: TestClient, headers: Headers, task_id: str, body: str) -> str:
    r = client.post(
        f"{API}/tasks/{task_id}/comments/", headers=headers, json={"body": body}
    )
    assert r.status_code == 200, r.text
    comment_id: str = r.json()["id"]
    return comment_id


def _attach(client: TestClient, headers: Headers, task_id: str) -> str:
    r = client.post(
        f"{API}/tasks/{task_id}/attachments/",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 200, r.text
    attachment_id: str = r.json()["id"]
    return attachment_id


# --- The matrix ---------------------------------------------------------------

# Each endpoint, the permission it needs, and how to call it on a task whose
# own attachment is `attachment_id`.
Call = Callable[[TestClient, Headers, str, str], Response]
ENDPOINTS: dict[str, tuple[str, Call]] = {
    "list comments": (
        "read_tasks",
        lambda c, h, task_id, _: c.get(f"{API}/tasks/{task_id}/comments/", headers=h),
    ),
    "add a comment": (
        "add_comments",
        lambda c, h, task_id, _: c.post(
            f"{API}/tasks/{task_id}/comments/", headers=h, json={"body": "Done"}
        ),
    ),
    "list attachments": (
        "read_tasks",
        lambda c, h, task_id, _: c.get(
            f"{API}/tasks/{task_id}/attachments/", headers=h
        ),
    ),
    "download an attachment": (
        "read_tasks",
        lambda c, h, _, attachment_id: c.get(
            f"{API}/attachments/{attachment_id}", headers=h
        ),
    ),
    "add an attachment": (
        "update_tasks",
        lambda c, h, task_id, _: c.post(
            f"{API}/tasks/{task_id}/attachments/",
            headers=h,
            files={"file": ("report.txt", b"report", "text/plain")},
        ),
    ),
    "delete an attachment": (
        "update_tasks",
        lambda c, h, _, attachment_id: c.delete(
            f"{API}/attachments/{attachment_id}", headers=h
        ),
    ),
}

CASES = {
    # case: (in scope, archived, permissions given the needed one, expected code)
    "allowed": (True, False, "only", None),
    "without the permission": (True, False, "all but", "permission_not_granted"),
    "outside the scope": (False, False, "all", "outside_scope"),
    "archived project": (True, True, "all", "project_archived"),
}


@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.parametrize("subtask", [False, True], ids=["task", "subtask"])
@pytest.mark.parametrize("endpoint", list(ENDPOINTS))
def test_each_endpoint_needs_its_permission_and_a_reachable_task(
    client: TestClient, db: Session, endpoint: str, subtask: bool, case: str
) -> None:
    permission, call = ENDPOINTS[endpoint]
    in_scope, archived, grant, expected = CASES[case]

    owner = create_user_headers(client, db)
    scoped = create_project(client, owner, "Scoped")
    unscoped = create_project(client, owner, "Unscoped")
    root = create_task(client, owner, project_id=scoped if in_scope else unscoped)
    task_id = create_task(client, owner, parent_id=root) if subtask else root
    _comment(client, owner, task_id, "From the owner")
    attachment_id = _attach(client, owner, task_id)
    permissions = {
        "only": {permission: True},
        "all but": {**ALL_PERMISSIONS, permission: False},
        "all": ALL_PERMISSIONS,
    }[grant]
    bot = issue_bot_headers(
        client, owner, project_ids=[scoped], permissions=permissions
    )
    if archived:
        r = client.post(f"{API}/projects/{scoped}/archive", headers=owner)
        assert r.status_code == 200

    r = call(client, bot, task_id, attachment_id)

    if expected is None:
        assert r.status_code == 200, r.text
    else:
        assert r.status_code == 403, r.text
        assert error_code(r) == expected
        # Nothing was added or removed on the way to the refusal.
        comments = client.get(f"{API}/tasks/{task_id}/comments/", headers=owner)
        attachments = client.get(f"{API}/tasks/{task_id}/attachments/", headers=owner)
        assert comments.json()["count"] == 1
        assert [a["id"] for a in attachments.json()["data"]] == [attachment_id]


def test_adding_a_comment_does_not_need_update_on_tasks(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id, title="Original")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions={"add_comments": True}
    )

    assert _comment(client, bot, task_id, "Working on it")
    # It reported without being able to change the task.
    r = client.patch(f"{API}/tasks/{task_id}", headers=bot, json={"title": "Changed"})
    assert error_code(r) == "permission_not_granted"


def test_a_bot_never_reaches_another_users_attachment(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    other = create_user_headers(client, db)
    other_attachment = _attach(client, other, create_task(client, other))
    bot = issue_bot_headers(
        client,
        owner,
        project_ids=[create_project(client, owner)],
        permissions=ALL_PERMISSIONS,
    )

    assert (
        client.get(f"{API}/attachments/{other_attachment}", headers=bot).status_code
        == 404
    )
    assert (
        client.delete(f"{API}/attachments/{other_attachment}", headers=bot).status_code
        == 404
    )


# --- A bot user's comments stay on the record ---------------------------------


def _bot_with_comment(
    client: TestClient, db: Session
) -> tuple[Headers, dict[str, Any], Headers, str, str]:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task_id = create_task(client, owner, project_id=project_id)
    bot_user = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Status bot",
    )
    bot = token_headers(client, owner, bot_user["id"])
    comment_id = _comment(client, bot, task_id, "Deployed to staging")
    return owner, bot_user, bot, task_id, comment_id


@pytest.mark.parametrize("verb", ["edit", "delete"])
def test_a_bot_cannot_edit_or_delete_even_its_own_comment(
    client: TestClient, db: Session, verb: str
) -> None:
    owner, _, bot, task_id, comment_id = _bot_with_comment(client, db)

    if verb == "edit":
        r = client.patch(
            f"{API}/comments/{comment_id}", headers=bot, json={"body": "Rewritten"}
        )
    else:
        r = client.delete(f"{API}/comments/{comment_id}", headers=bot)
    # Refused for being a bot user, whatever it was granted.
    assert r.status_code == 403
    assert error_code(r) == "human_only"

    comments = client.get(f"{API}/tasks/{task_id}/comments/", headers=owner).json()
    assert [c["body"] for c in comments["data"]] == ["Deployed to staging"]


@pytest.mark.parametrize("verb", ["edit", "delete"])
def test_the_owner_cannot_edit_or_delete_a_bot_users_comment(
    client: TestClient, db: Session, verb: str
) -> None:
    owner, _, _, task_id, comment_id = _bot_with_comment(client, db)

    if verb == "edit":
        r = client.patch(
            f"{API}/comments/{comment_id}", headers=owner, json={"body": "Rewritten"}
        )
    else:
        r = client.delete(f"{API}/comments/{comment_id}", headers=owner)
    assert r.status_code == 403
    assert error_code(r) == "comment_by_bot"

    comments = client.get(f"{API}/tasks/{task_id}/comments/", headers=owner).json()
    assert [c["body"] for c in comments["data"]] == ["Deployed to staging"]


def test_a_comment_names_the_bot_user_that_wrote_it(
    client: TestClient, db: Session
) -> None:
    owner, bot_user, bot, task_id, _ = _bot_with_comment(client, db)
    _comment(client, owner, task_id, "Thanks")

    for headers in (owner, bot):
        comments = client.get(f"{API}/tasks/{task_id}/comments/", headers=headers)
        authors = [(c["body"], c["author_bot_user"]) for c in comments.json()["data"]]
        assert authors == [
            (
                "Deployed to staging",
                {"id": bot_user["id"], "name": "Status bot", "deleted": False},
            ),
            ("Thanks", None),
        ]


# --- Attribution --------------------------------------------------------------


def test_comments_and_attachments_a_bot_adds_are_logged_as_the_bots(
    client: TestClient, db: Session
) -> None:
    owner, bot_user, bot, task_id, comment_id = _bot_with_comment(client, db)
    attachment_id = _attach(client, bot, task_id)
    r = client.delete(f"{API}/attachments/{attachment_id}", headers=bot)
    assert r.status_code == 200, r.text

    entries = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    by_entity = {
        (e["action"], e["entity_id"]): e
        for e in entries
        if e["action"] in {"comment_added", "attachment_added", "attachment_deleted"}
    }
    assert set(by_entity) == {
        ("comment_added", comment_id),
        ("attachment_added", attachment_id),
        ("attachment_deleted", attachment_id),
    }
    for entry in by_entity.values():
        assert entry["actor_bot_user_id"] == bot_user["id"]
        assert entry["actor_id"] is None
