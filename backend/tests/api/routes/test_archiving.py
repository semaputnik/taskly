import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, func, select

from app import crud
from app.api.deps import get_attachment_storage
from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.models import Deletion, Project, UserCreate
from tests.api.routes.test_attachments import InMemoryAttachmentStorage
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR
YESTERDAY = date.today() - timedelta(days=1)


@pytest.fixture(autouse=True)
def storage():
    fake_storage = InMemoryAttachmentStorage()
    app.dependency_overrides[get_attachment_storage] = lambda: fake_storage
    yield fake_storage
    del app.dependency_overrides[get_attachment_storage]


def _headers_for_new_user(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    crud.create_user(session=db, user_create=user_in)

    login_data = {"username": email, "password": password}
    r = client.post(f"{API}/login/access-token", data=login_data)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _me(client: TestClient, headers: dict[str, str]) -> str:
    return client.get(f"{API}/users/me", headers=headers).json()["id"]


def _inbox_id(client: TestClient, headers: dict[str, str]) -> str:
    r = client.get(f"{API}/projects/", headers=headers)
    return next(p["id"] for p in r.json()["data"] if p["is_inbox"])


def _create_project(client: TestClient, headers: dict[str, str], name: str) -> str:
    r = client.post(f"{API}/projects/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_task(
    client: TestClient, headers: dict[str, str], title: str, **fields: object
) -> dict:
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": title, **fields})
    assert r.status_code == 200, r.text
    return r.json()


def _archive(
    client: TestClient, headers: dict[str, str], project_id: str
) -> httpx.Response:
    return client.post(f"{API}/projects/{project_id}/archive", headers=headers)


def _unarchive(
    client: TestClient, headers: dict[str, str], project_id: str
) -> httpx.Response:
    return client.post(f"{API}/projects/{project_id}/unarchive", headers=headers)


def _project_ids(
    client: TestClient, headers: dict[str, str], **params: object
) -> set[str]:
    r = client.get(f"{API}/projects/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == len(body["data"])
    return {p["id"] for p in body["data"]}


def _tasks(client: TestClient, headers: dict[str, str], **params: object) -> dict:
    r = client.get(f"{API}/tasks/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return {t["title"]: t for t in r.json()["data"]}


def _listed_titles(
    client: TestClient, headers: dict[str, str], **params: object
) -> set[str]:
    return set(_tasks(client, headers, **params))


@dataclass
class Account:
    """
    A user with one live project and one archived project, each holding the
    same shape of work: a root task carrying every filterable field, a subtask
    under it, a comment and an attachment.
    """

    headers: dict[str, str]
    user_id: str
    live_project: str
    archived_project: str
    archived_root: dict
    archived_subtask: dict
    archived_comment: dict
    archived_attachment: dict


def _fill_project(
    client: TestClient, headers: dict[str, str], project_id: str, prefix: str
) -> tuple[dict, dict, dict, dict]:
    root = _create_task(
        client,
        headers,
        f"{prefix} root",
        project_id=project_id,
        tags=["focus"],
        priority="P1",
        due_date=YESTERDAY.isoformat(),
        assignee_id=_me(client, headers),
    )
    subtask = _create_task(client, headers, f"{prefix} subtask", parent_id=root["id"])
    r = client.post(
        f"{API}/tasks/{root['id']}/comments/", headers=headers, json={"body": "Note"}
    )
    assert r.status_code == 200, r.text
    comment = r.json()
    r = client.post(
        f"{API}/tasks/{root['id']}/attachments/",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 200, r.text
    return root, subtask, comment, r.json()


def _account(client: TestClient, db: Session) -> Account:
    headers = _headers_for_new_user(client, db)
    live = _create_project(client, headers, "Live")
    archived = _create_project(client, headers, "Shelved")
    _fill_project(client, headers, live, "Live")
    root, subtask, comment, attachment = _fill_project(
        client, headers, archived, "Shelved"
    )
    r = _archive(client, headers, archived)
    assert r.status_code == 200, r.text
    return Account(
        headers=headers,
        user_id=_me(client, headers),
        live_project=live,
        archived_project=archived,
        archived_root=root,
        archived_subtask=subtask,
        archived_comment=comment,
        archived_attachment=attachment,
    )


# --- The toggle ---------------------------------------------------------------


def test_archive_and_unarchive_a_project_repeatedly(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Side project")

    for _ in range(2):
        r = _archive(client, headers, project_id)
        assert r.status_code == 200, r.text
        assert r.json()["is_archived"] is True
        assert project_id not in _project_ids(client, headers)
        assert project_id in _project_ids(client, headers, archived=True)

        r = _unarchive(client, headers, project_id)
        assert r.status_code == 200, r.text
        assert r.json()["is_archived"] is False
        assert project_id in _project_ids(client, headers)
        assert project_id not in _project_ids(client, headers, archived=True)


def test_archiving_is_idempotent(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Side project")

    assert _archive(client, headers, project_id).status_code == 200
    r = _archive(client, headers, project_id)
    assert r.status_code == 200
    assert r.json()["is_archived"] is True

    assert _unarchive(client, headers, project_id).status_code == 200
    r = _unarchive(client, headers, project_id)
    assert r.status_code == 200
    assert r.json()["is_archived"] is False


def test_the_inbox_cannot_be_archived(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    inbox_id = _inbox_id(client, headers)

    r = _archive(client, headers, inbox_id)
    assert r.status_code == 400
    assert r.json()["detail"] == "The Inbox project cannot be archived"
    assert inbox_id in _project_ids(client, headers)


def test_another_users_project_cannot_be_archived_or_unarchived(
    client: TestClient, db: Session
) -> None:
    owner = _headers_for_new_user(client, db)
    stranger = _headers_for_new_user(client, db)
    project_id = _create_project(client, owner, "Private")

    assert _archive(client, stranger, project_id).status_code == 404
    assert project_id in _project_ids(client, owner)

    assert _archive(client, owner, project_id).status_code == 200
    assert _unarchive(client, stranger, project_id).status_code == 404
    assert project_id in _project_ids(client, owner, archived=True)


# --- The derived cascade ------------------------------------------------------


@contextmanager
def _statements() -> Iterator[list[str]]:
    """Every SQL statement the application sends while the block runs."""
    seen: list[str] = []

    def record(_conn, _cursor, statement, _params, _context, _executemany) -> None:
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_archiving_writes_nothing_but_the_project(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Shelved")
    root = _create_task(client, headers, "Root", project_id=project_id)
    _create_task(client, headers, "Child", parent_id=root["id"])

    for toggle in (_archive, _unarchive):
        with _statements() as seen:
            assert toggle(client, headers, project_id).status_code == 200
        writes = [
            s
            for s in seen
            if s.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE"))
        ]
        assert writes, "the project itself has to be written"
        assert all(s.lstrip().upper().startswith("UPDATE PROJECT") for s in writes), (
            writes
        )


def test_archiving_hides_every_task_of_the_project_including_subtasks(
    client: TestClient, db: Session
) -> None:
    account = _account(client, db)

    assert _listed_titles(client, account.headers) == {"Live root", "Live subtask"}
    assert _listed_titles(client, account.headers, archived=True) == {
        "Shelved root",
        "Shelved subtask",
    }


def test_unarchiving_brings_every_task_back_exactly_as_it_was(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Shelved")
    root = _create_task(
        client, headers, "Root", project_id=project_id, tags=["a"], priority="P2"
    )
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    r = client.patch(
        f"{API}/tasks/{child['id']}", headers=headers, json={"completed": True}
    )
    assert r.status_code == 200, r.text

    before = _tasks(client, headers)
    assert before["Child"]["completed"] is True

    assert _archive(client, headers, project_id).status_code == 200
    assert _tasks(client, headers) == {}
    assert _tasks(client, headers, archived=True) == before

    assert _unarchive(client, headers, project_id).status_code == 200
    assert _tasks(client, headers) == before
    assert _tasks(client, headers, archived=True) == {}


# --- Read-only ----------------------------------------------------------------


def _create_root_task(client: TestClient, a: Account) -> httpx.Response:
    return client.post(
        f"{API}/tasks/",
        headers=a.headers,
        json={"title": "New", "project_id": a.archived_project},
    )


def _create_subtask(client: TestClient, a: Account) -> httpx.Response:
    return client.post(
        f"{API}/tasks/",
        headers=a.headers,
        json={"title": "New", "parent_id": a.archived_subtask["id"]},
    )


def _edit_task(client: TestClient, a: Account) -> httpx.Response:
    return client.patch(
        f"{API}/tasks/{a.archived_subtask['id']}",
        headers=a.headers,
        json={"title": "Renamed"},
    )


def _complete_task(client: TestClient, a: Account) -> httpx.Response:
    return client.patch(
        f"{API}/tasks/{a.archived_subtask['id']}",
        headers=a.headers,
        json={"completed": True},
    )


def _reopen_task(client: TestClient, a: Account) -> httpx.Response:
    return client.patch(
        f"{API}/tasks/{a.archived_subtask['id']}",
        headers=a.headers,
        json={"completed": False},
    )


def _delete_task(client: TestClient, a: Account) -> httpx.Response:
    return client.delete(f"{API}/tasks/{a.archived_subtask['id']}", headers=a.headers)


def _move_task_out(client: TestClient, a: Account) -> httpx.Response:
    return client.patch(
        f"{API}/tasks/{a.archived_root['id']}",
        headers=a.headers,
        json={"project_id": a.live_project},
    )


def _move_task_in(client: TestClient, a: Account) -> httpx.Response:
    task = _create_task(client, a.headers, "Mover", project_id=a.live_project)
    return client.patch(
        f"{API}/tasks/{task['id']}",
        headers=a.headers,
        json={"project_id": a.archived_project},
    )


def _edit_project(client: TestClient, a: Account) -> httpx.Response:
    return client.patch(
        f"{API}/projects/{a.archived_project}",
        headers=a.headers,
        json={"description": "Changed"},
    )


def _add_comment(client: TestClient, a: Account) -> httpx.Response:
    return client.post(
        f"{API}/tasks/{a.archived_subtask['id']}/comments/",
        headers=a.headers,
        json={"body": "Late thought"},
    )


def _edit_comment(client: TestClient, a: Account) -> httpx.Response:
    return client.patch(
        f"{API}/comments/{a.archived_comment['id']}",
        headers=a.headers,
        json={"body": "Rewritten"},
    )


def _delete_comment(client: TestClient, a: Account) -> httpx.Response:
    return client.delete(
        f"{API}/comments/{a.archived_comment['id']}", headers=a.headers
    )


def _upload_attachment(client: TestClient, a: Account) -> httpx.Response:
    return client.post(
        f"{API}/tasks/{a.archived_subtask['id']}/attachments/",
        headers=a.headers,
        files={"file": ("late.txt", b"late", "text/plain")},
    )


def _delete_attachment(client: TestClient, a: Account) -> httpx.Response:
    return client.delete(
        f"{API}/attachments/{a.archived_attachment['id']}", headers=a.headers
    )


REFUSED_WRITES: list[Callable[[TestClient, Account], httpx.Response]] = [
    _create_root_task,
    _create_subtask,
    _edit_task,
    _complete_task,
    _reopen_task,
    _delete_task,
    _move_task_out,
    _move_task_in,
    _edit_project,
    _add_comment,
    _edit_comment,
    _delete_comment,
    _upload_attachment,
    _delete_attachment,
]


@pytest.mark.parametrize("write", REFUSED_WRITES, ids=lambda w: w.__name__[1:])
def test_writes_inside_an_archived_project_are_refused(
    client: TestClient,
    db: Session,
    write: Callable[[TestClient, Account], httpx.Response],
) -> None:
    account = _account(client, db)
    archive_before = _tasks(client, account.headers, archived=True)

    r = write(client, account)

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "project_archived"
    assert detail["project_id"] == account.archived_project

    # Nothing moved in, out, or changed.
    assert _tasks(client, account.headers, archived=True) == archive_before
    project = next(
        p
        for p in client.get(
            f"{API}/projects/", headers=account.headers, params={"archived": True}
        ).json()["data"]
        if p["id"] == account.archived_project
    )
    assert project["description"] is None
    task_id = account.archived_root["id"]
    comments = client.get(f"{API}/tasks/{task_id}/comments/", headers=account.headers)
    assert [c["body"] for c in comments.json()["data"]] == ["Note"]
    attachments = client.get(
        f"{API}/tasks/{task_id}/attachments/", headers=account.headers
    )
    assert attachments.json()["count"] == 1


@pytest.mark.parametrize("write", REFUSED_WRITES, ids=lambda w: w.__name__[1:])
def test_the_same_writes_succeed_once_unarchived(
    client: TestClient,
    db: Session,
    write: Callable[[TestClient, Account], httpx.Response],
) -> None:
    account = _account(client, db)
    r = _unarchive(client, account.headers, account.archived_project)
    assert r.status_code == 200, r.text

    r = write(client, account)
    assert r.status_code == 200, r.text


def test_an_archived_project_stays_readable(client: TestClient, db: Session) -> None:
    account = _account(client, db)
    task_id = account.archived_root["id"]

    r = client.get(f"{API}/tasks/{task_id}", headers=account.headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Shelved root"

    r = client.get(f"{API}/tasks/{task_id}/comments/", headers=account.headers)
    assert r.status_code == 200
    assert r.json()["count"] == 1

    r = client.get(f"{API}/tasks/{task_id}/attachments/", headers=account.headers)
    assert r.status_code == 200
    assert r.json()["count"] == 1

    r = client.get(
        f"{API}/attachments/{account.archived_attachment['id']}",
        headers=account.headers,
    )
    assert r.status_code == 200
    assert r.content == b"hello"


# --- Listings -----------------------------------------------------------------


# Each of these matches both projects' root task, so an archived task showing
# up in the default list would be the filter letting it through.
FILTERS: list[dict[str, object]] = [
    {"tag": "focus"},
    {"priority": "P1"},
    {"completed": False},
    {"due_from": YESTERDAY.isoformat(), "due_to": YESTERDAY.isoformat()},
    {"overdue": True},
    {"assignee": "me"},
    {"sort": "due_date", "order": "desc"},
    {"sort": "priority"},
]


@pytest.mark.parametrize("filters", FILTERS, ids=lambda f: ",".join(f))
def test_filters_leave_archived_tasks_out_unless_the_archive_is_asked_for(
    client: TestClient, db: Session, filters: dict[str, object]
) -> None:
    account = _account(client, db)
    params = dict(filters)
    if params.pop("assignee", None) == "me":
        params["assignee_id"] = account.user_id

    default = _listed_titles(client, account.headers, **params)
    assert "Live root" in default
    assert not {"Shelved root", "Shelved subtask"} & default

    archive = _listed_titles(client, account.headers, archived=True, **params)
    assert "Shelved root" in archive
    assert not {"Live root", "Live subtask"} & archive


def test_unassigned_filter_leaves_archived_tasks_out(
    client: TestClient, db: Session
) -> None:
    account = _account(client, db)

    assert _listed_titles(client, account.headers, unassigned=True) == {"Live subtask"}
    assert _listed_titles(client, account.headers, archived=True, unassigned=True) == {
        "Shelved subtask"
    }


def test_filtering_by_an_archived_project_needs_the_archive(
    client: TestClient, db: Session
) -> None:
    account = _account(client, db)
    project_id = account.archived_project

    r = client.get(
        f"{API}/tasks/", headers=account.headers, params={"project_id": project_id}
    )
    assert r.status_code == 200
    assert r.json() == {"data": [], "count": 0}

    assert _listed_titles(
        client, account.headers, project_id=project_id, archived=True
    ) == {"Shelved root", "Shelved subtask"}


def test_the_archive_count_pages_through_archived_tasks_only(
    client: TestClient, db: Session
) -> None:
    account = _account(client, db)

    r = client.get(
        f"{API}/tasks/", headers=account.headers, params={"archived": True, "limit": 1}
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2
    assert len(r.json()["data"]) == 1


# --- Archived and deleted are different states -------------------------------


def _deletions(db: Session, project_id: str) -> int:
    db.expire_all()
    return db.exec(
        select(func.count())
        .select_from(Deletion)
        .where(Deletion.project_id == uuid.UUID(project_id))
    ).one()


def test_archiving_is_not_a_deletion(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers, "Shelved")
    root = _create_task(client, headers, "Root", project_id=project_id)

    assert _archive(client, headers, project_id).status_code == 200
    assert _unarchive(client, headers, project_id).status_code == 200

    assert _deletions(db, project_id) == 0
    project = db.get(Project, uuid.UUID(project_id))
    assert project is not None and project.deletion_id is None
    r = client.get(f"{API}/tasks/{root['id']}", headers=headers)
    assert r.status_code == 200


def test_an_archived_project_can_be_deleted(client: TestClient, db: Session) -> None:
    account = _account(client, db)
    project_id = account.archived_project

    r = client.delete(f"{API}/projects/{project_id}", headers=account.headers)
    assert r.status_code == 200, r.text

    assert project_id not in _project_ids(client, account.headers)
    assert project_id not in _project_ids(client, account.headers, archived=True)
    assert _listed_titles(client, account.headers, archived=True) == set()
    assert _deletions(db, project_id) == 1

    # The two states sit side by side rather than one replacing the other.
    project = db.get(Project, uuid.UUID(project_id))
    assert project is not None
    assert project.is_archived is True
    assert project.deletion_id is not None

    # A deleted project is gone for the toggle too.
    assert _unarchive(client, account.headers, project_id).status_code == 404
