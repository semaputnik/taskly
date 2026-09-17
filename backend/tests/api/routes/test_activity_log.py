import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import activity, crud
from app.api.deps import get_attachment_storage
from app.core.config import settings
from app.main import app
from app.models import ActivityEntry, TaskCreate, UserCreate
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
    user_in = UserCreate(email=email, password=password)
    crud.create_user(session=db, user_create=user_in)

    login_data = {"username": email, "password": password}
    r = client.post(f"{API}/login/access-token", data=login_data)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _me(client: TestClient, headers: dict[str, str]) -> str:
    return client.get(f"{API}/users/me", headers=headers).json()["id"]


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


def _patch(
    client: TestClient, headers: dict[str, str], task_id: str, **fields: object
) -> dict:
    r = client.patch(f"{API}/tasks/{task_id}", headers=headers, json=fields)
    assert r.status_code == 200, r.text
    return r.json()


def _log(client: TestClient, headers: dict[str, str], **params: object) -> list[dict]:
    """The user's log, oldest first, which is how the tests read a sequence."""
    r = client.get(f"{API}/activity-log/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return list(reversed(r.json()["data"]))


def _log_after(
    client: TestClient, headers: dict[str, str], seen: list[dict]
) -> list[dict]:
    """The entries added since `seen` was read."""
    return _log(client, headers)[len(seen) :]


# --- Each task action ---------------------------------------------------------


def test_creating_a_task_is_logged(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")

    task = _create_task(
        client,
        headers,
        "Fix the tap",
        project_id=project["id"],
        priority="P2",
        tags=["plumbing"],
    )

    [entry] = [e for e in _log(client, headers) if e["entity_type"] == "task"]
    assert entry["action"] == "task_created"
    assert entry["entity_type"] == "task"
    assert entry["entity_id"] == task["id"]
    assert entry["actor_id"] == _me(client, headers)
    assert entry["created_at"] is not None
    assert entry["details"]["title"] == "Fix the tap"
    snapshot = entry["details"]["task"]
    assert snapshot["project"] == {"id": project["id"], "name": "Home"}
    assert snapshot["priority"] == "P2"
    assert snapshot["tags"] == ["plumbing"]
    assert snapshot["status"] == "todo"


def test_changing_a_task_is_logged_with_what_changed(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Fix the tap", tags=["home"])
    seen = _log(client, headers)

    _patch(
        client,
        headers,
        task["id"],
        title="Fix the kitchen tap",
        description="Drips at night",
        due_date="2026-03-02",
        priority="P1",
        tags=["home", "plumbing"],
    )

    # "plumbing" is a tag the user did not have: typing it creates it, and that
    # is logged first, as its own entry (FR-10.3).
    created, entry = _log_after(client, headers, seen)
    assert created["action"] == "tag_created"
    assert created["details"] == {"name": "plumbing"}
    assert entry["action"] == "task_changed"
    assert entry["details"]["title"] == "Fix the kitchen tap"
    assert entry["details"]["changes"] == {
        "title": {"from": "Fix the tap", "to": "Fix the kitchen tap"},
        "description": {"from": None, "to": "Drips at night"},
        "due_date": {"from": None, "to": "2026-03-02"},
        "priority": {"from": None, "to": "P1"},
        "tags": {"from": ["home"], "to": ["home", "plumbing"]},
    }


def test_changing_how_a_task_recurs_is_logged(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Water plants", due_date="2026-03-02")
    seen = _log(client, headers)

    _patch(client, headers, task["id"], recurrence={"frequency": "weekly"})

    [entry] = _log_after(client, headers, seen)
    assert entry["action"] == "task_changed"
    assert entry["details"]["changes"] == {
        "recurrence": {
            "from": None,
            "to": {"frequency": "weekly", "interval_days": None},
        }
    }


def test_moving_a_task_is_logged_with_both_projects(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    home = _create_project(client, headers, "Home")
    work = _create_project(client, headers, "Work")
    task = _create_task(client, headers, "Print the report", project_id=home["id"])
    seen = _log(client, headers)

    _patch(client, headers, task["id"], project_id=work["id"])

    [entry] = _log_after(client, headers, seen)
    assert entry["action"] == "task_moved"
    assert entry["details"]["from_project"] == {"id": home["id"], "name": "Home"}
    assert entry["details"]["to_project"] == {"id": work["id"], "name": "Work"}


def test_setting_and_removing_an_assignee_are_logged(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    me = _me(client, headers)
    task = _create_task(client, headers, "Call the bank")
    seen = _log(client, headers)

    _patch(client, headers, task["id"], assignee_id=me)
    _patch(client, headers, task["id"], assignee_id=None)

    assigned, unassigned = _log_after(client, headers, seen)
    assert assigned["action"] == "task_assigned"
    assert assigned["details"]["assignee_id"] == me
    assert unassigned["action"] == "task_unassigned"
    assert unassigned["details"]["previous_assignee_id"] == me


def test_completing_and_reopening_a_task_are_logged(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Call the bank")
    seen = _log(client, headers)

    _patch(client, headers, task["id"], status="done")
    _patch(client, headers, task["id"], status="todo")

    actions = [e["action"] for e in _log_after(client, headers, seen)]
    assert actions == ["task_completed", "task_reopened"]


def test_deleting_a_task_is_one_entry_for_the_whole_deletion(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    root = _create_task(client, headers, "Move house", project_id=project["id"])
    child = _create_task(client, headers, "Pack", parent_id=root["id"])
    _create_task(client, headers, "Books", parent_id=child["id"])
    seen = _log(client, headers)

    r = client.delete(
        f"{API}/tasks/{root['id']}",
        headers=headers,
        params={"delete_subtasks": True},
    )
    assert r.status_code == 200

    [entry] = _log_after(client, headers, seen)
    assert entry["action"] == "task_deleted"
    assert entry["entity_id"] == root["id"]
    assert entry["deletion_id"] is not None
    assert entry["details"]["title"] == "Move house"
    assert entry["details"]["project"] == {"id": project["id"], "name": "Home"}
    assert entry["details"]["subtask_count"] == 2


# --- Projects, comments and attachments ---------------------------------------


def test_a_new_account_starts_with_an_empty_log(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    # The Inbox comes with the account; nobody made it.
    assert _log(client, headers) == []


def test_creating_a_project_is_logged(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{API}/projects/",
        headers=headers,
        json={"name": "Home", "description": "Around the flat"},
    )
    project = r.json()

    [entry] = _log(client, headers)
    assert entry["action"] == "project_created"
    assert entry["entity_type"] == "project"
    assert entry["entity_id"] == project["id"]
    assert entry["actor_id"] == _me(client, headers)
    assert entry["details"] == {"name": "Home", "description": "Around the flat"}
    assert entry["entity_exists"] is True
    assert entry["entity_project_id"] == project["id"]


def test_changing_a_project_is_logged_with_what_changed(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    seen = _log(client, headers)

    r = client.patch(
        f"{API}/projects/{project['id']}",
        headers=headers,
        json={"name": "Flat", "description": "Second floor"},
    )
    assert r.status_code == 200

    [entry] = _log_after(client, headers, seen)
    assert entry["action"] == "project_changed"
    assert entry["details"]["name"] == "Flat"
    assert entry["details"]["changes"] == {
        "name": {"from": "Home", "to": "Flat"},
        "description": {"from": None, "to": "Second floor"},
    }


def test_deleting_a_project_is_one_entry_for_the_whole_deletion(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Someday")
    root = _create_task(client, headers, "Learn the cello", project_id=project["id"])
    _create_task(client, headers, "Find a teacher", parent_id=root["id"])
    _create_task(client, headers, "Read more", project_id=project["id"])
    seen = _log(client, headers)

    r = client.delete(f"{API}/projects/{project['id']}", headers=headers)
    assert r.status_code == 200

    [entry] = _log_after(client, headers, seen)
    assert entry["action"] == "project_deleted"
    assert entry["entity_id"] == project["id"]
    assert entry["deletion_id"] is not None
    assert entry["details"] == {"name": "Someday", "task_count": 3}
    assert entry["entity_exists"] is False


def test_adding_editing_and_deleting_a_comment_are_logged(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    task = _create_task(client, headers, "Fix the tap", project_id=project["id"])
    seen = _log(client, headers)

    r = client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=headers, json={"body": "Drips"}
    )
    comment = r.json()
    r = client.patch(
        f"{API}/comments/{comment['id']}", headers=headers, json={"body": "Pours"}
    )
    assert r.status_code == 200
    r = client.delete(f"{API}/comments/{comment['id']}", headers=headers)
    assert r.status_code == 200

    added, edited, deleted = _log_after(client, headers, seen)
    task_ref = {"id": task["id"], "title": "Fix the tap"}
    assert added["action"] == "comment_added"
    assert added["entity_type"] == "comment"
    assert added["entity_id"] == comment["id"]
    assert added["details"] == {"task": task_ref, "body": "Drips"}
    assert edited["action"] == "comment_edited"
    assert edited["details"] == {
        "task": task_ref,
        "changes": {"body": {"from": "Drips", "to": "Pours"}},
    }
    assert deleted["action"] == "comment_deleted"
    assert deleted["details"] == {"task": task_ref, "body": "Pours"}
    # The comment is gone, so none of its entries link anywhere.
    assert all(e["entity_exists"] is False for e in (added, edited, deleted))


def test_a_comment_entry_links_to_its_task_while_both_exist(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    task = _create_task(client, headers, "Fix the tap", project_id=project["id"])
    client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=headers, json={"body": "Drips"}
    )

    [entry] = [e for e in _log(client, headers) if e["entity_type"] == "comment"]
    assert entry["entity_exists"] is True
    assert entry["entity_project_id"] == project["id"]

    r = client.delete(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200
    [entry] = [e for e in _log(client, headers) if e["entity_type"] == "comment"]
    assert entry["entity_exists"] is False


def test_adding_and_deleting_an_attachment_are_logged(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Fix the tap")
    seen = _log(client, headers)

    r = client.post(
        f"{API}/tasks/{task['id']}/attachments/",
        headers=headers,
        files={"file": ("quote.pdf", b"%PDF-1.7", "application/pdf")},
    )
    attachment = r.json()
    r = client.delete(f"{API}/attachments/{attachment['id']}", headers=headers)
    assert r.status_code == 200

    added, deleted = _log_after(client, headers, seen)
    details = {
        "task": {"id": task["id"], "title": "Fix the tap"},
        "filename": "quote.pdf",
        "content_type": "application/pdf",
        "size": 8,
    }
    assert added["action"] == "attachment_added"
    assert added["entity_type"] == "attachment"
    assert added["entity_id"] == attachment["id"]
    assert added["details"] == details
    assert deleted["action"] == "attachment_deleted"
    assert deleted["details"] == details


def test_a_refused_upload_writes_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Fix the tap")
    seen = _log(client, headers)
    monkeypatch.setattr(settings, "ATTACHMENT_MAX_SIZE_BYTES", 4)

    r = client.post(
        f"{API}/tasks/{task['id']}/attachments/",
        headers=headers,
        files={"file": ("big.bin", b"too large", "application/octet-stream")},
    )
    assert r.status_code == 413

    assert _log_after(client, headers, seen) == []


# --- How requests map to entries ----------------------------------------------


def test_one_request_with_several_changes_writes_an_entry_for_each(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    work = _create_project(client, headers, "Work")
    task = _create_task(client, headers, "Print the report")
    seen = _log(client, headers)

    _patch(
        client,
        headers,
        task["id"],
        title="Print the quarterly report",
        project_id=work["id"],
        assignee_id=_me(client, headers),
        status="done",
    )

    actions = [e["action"] for e in _log_after(client, headers, seen)]
    assert sorted(actions) == [
        "task_assigned",
        "task_changed",
        "task_completed",
        "task_moved",
    ]


def test_resending_unchanged_fields_writes_nothing(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Call the bank", tags=["money"])
    seen = _log(client, headers)

    _patch(
        client,
        headers,
        task["id"],
        title="Call the bank",
        description=None,
        tags=["money"],
        status="todo",
    )

    assert _log_after(client, headers, seen) == []


def test_completing_subtasks_along_with_their_parent_logs_each_completion(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Move house")
    child = _create_task(client, headers, "Pack", parent_id=root["id"])
    grandchild = _create_task(client, headers, "Books", parent_id=child["id"])
    seen = _log(client, headers)

    _patch(client, headers, root["id"], status="done", subtasks="complete")

    completed = {
        e["entity_id"]
        for e in _log_after(client, headers, seen)
        if e["action"] == "task_completed"
    }
    assert completed == {root["id"], child["id"], grandchild["id"]}


def test_completing_a_recurring_task_logs_the_next_occurrence(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(
        client,
        headers,
        "Water plants",
        due_date="2026-03-02",
        recurrence={"frequency": "weekly"},
    )
    seen = _log(client, headers)

    _patch(client, headers, task["id"], status="done")

    completed, created = _log_after(client, headers, seen)
    assert completed["action"] == "task_completed"
    assert completed["entity_id"] == task["id"]
    assert created["action"] == "task_created"
    assert created["entity_id"] != task["id"]
    assert created["details"]["task"]["due_date"] == "2026-03-09"


def test_archiving_a_project_is_not_logged(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Someday")
    _create_task(client, headers, "Learn the cello", project_id=project["id"])
    seen = _log(client, headers)

    for toggle in ("archive", "unarchive"):
        r = client.post(f"{API}/projects/{project['id']}/{toggle}", headers=headers)
        assert r.status_code == 200

    assert _log_after(client, headers, seen) == []


def test_a_refused_change_writes_nothing(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Move house")
    _create_task(client, headers, "Pack", parent_id=root["id"])
    seen = _log(client, headers)

    r = client.patch(
        f"{API}/tasks/{root['id']}",
        headers=headers,
        json={"title": "Move flat", "status": "done"},
    )
    assert r.status_code == 409

    assert _log_after(client, headers, seen) == []


def test_a_change_and_its_entry_commit_together(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Call the bank")
    seen = _log(client, headers)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("log is unwritable")

    monkeypatch.setattr(activity, "_task_entries", fail)
    with pytest.raises(RuntimeError):
        client.patch(
            f"{API}/tasks/{task['id']}", headers=headers, json={"title": "Changed"}
        )
    monkeypatch.undo()

    r = client.get(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.json()["title"] == "Call the bank"
    assert _log_after(client, headers, seen) == []


def test_entries_stay_readable_after_the_task_is_deleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Old title")
    _patch(client, headers, task["id"], title="New title")
    r = client.delete(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200

    created, changed, deleted = _log(client, headers)
    assert created["details"]["title"] == "Old title"
    assert changed["details"]["changes"]["title"] == {
        "from": "Old title",
        "to": "New title",
    }
    assert deleted["details"]["title"] == "New title"
    assert all(entry["entity_exists"] is False for entry in (created, changed))


def test_an_entry_says_where_its_task_can_still_be_opened(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    project = _create_project(client, headers, "Home")
    root = _create_task(client, headers, "Move house", project_id=project["id"])
    _create_task(client, headers, "Pack", parent_id=root["id"])

    for entry in _log(client, headers):
        assert entry["entity_exists"] is True
        assert entry["entity_project_id"] == project["id"]


# --- Reading the log ----------------------------------------------------------


def test_the_log_is_newest_first_and_pages(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    for title in ("First", "Second", "Third"):
        _create_task(client, headers, title)

    r = client.get(f"{API}/activity-log/", headers=headers)
    body = r.json()
    assert body["count"] == 3
    assert [e["details"]["title"] for e in body["data"]] == [
        "Third",
        "Second",
        "First",
    ]

    r = client.get(
        f"{API}/activity-log/", headers=headers, params={"skip": 1, "limit": 1}
    )
    body = r.json()
    assert body["count"] == 3
    assert [e["details"]["title"] for e in body["data"]] == ["Second"]


def test_a_user_sees_only_their_own_log(client: TestClient, db: Session) -> None:
    mine = _headers_for_new_user(client, db)
    theirs = _headers_for_new_user(client, db)
    _create_task(client, mine, "Mine")
    _create_task(client, theirs, "Theirs")

    assert [e["details"]["title"] for e in _log(client, mine)] == ["Mine"]
    assert [e["details"]["title"] for e in _log(client, theirs)] == ["Theirs"]


def test_the_superuser_sees_only_their_own_log(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    other = _headers_for_new_user(client, db)
    other_task = _create_task(client, other, "Someone else's secret")
    _create_task(client, superuser_token_headers, "Superuser's own")

    entries = _log(client, superuser_token_headers, limit=200)
    superuser_id = _me(client, superuser_token_headers)
    assert all(e["actor_id"] == superuser_id for e in entries)
    assert other_task["id"] not in {e["entity_id"] for e in entries}
    assert "Superuser's own" in {e["details"]["title"] for e in entries}


def test_the_log_needs_a_signed_in_user(client: TestClient) -> None:
    r = client.get(f"{API}/activity-log/")
    assert r.status_code == 401


def test_a_change_made_outside_a_request_is_attributed_to_the_owner(
    db: Session,
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)

    crud.create_task(
        session=db,
        task_create=TaskCreate(title="From a script"),
        project_id=inbox.id,
        owner_id=user.id,
    )

    [entry] = db.exec(
        select(ActivityEntry).where(ActivityEntry.owner_id == user.id)
    ).all()
    assert entry.action == "task_created"
    assert entry.actor_id == user.id


def test_a_change_committed_without_a_flush_of_its_own_is_logged(
    db: Session,
) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    inbox = crud.get_inbox_project(session=db, owner_id=user.id)
    task = crud.create_task(
        session=db,
        task_create=TaskCreate(title="Before"),
        project_id=inbox.id,
        owner_id=user.id,
    )

    # Nothing flushes between the change and the commit.
    task.title = "After"
    db.add(task)
    db.commit()

    entries = db.exec(
        select(ActivityEntry)
        .where(ActivityEntry.owner_id == user.id)
        .order_by(col(ActivityEntry.position))
    ).all()
    assert [entry.action for entry in entries] == ["task_created", "task_changed"]
    assert entries[1].details["changes"] == {"title": {"from": "Before", "to": "After"}}
