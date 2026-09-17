import uuid
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.api.deps import get_attachment_storage
from app.core.config import settings
from app.main import app
from app.models import Task, TaskStatus, UserCreate
from tests.api.routes.test_attachments import InMemoryAttachmentStorage
from tests.utils.bot import create_project, create_user_headers, issue_bot_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR
WEEKLY = {"frequency": "weekly"}


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


def _create_task(
    client: TestClient, headers: dict[str, str], title: str, **fields: object
) -> dict:
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": title, **fields})
    assert r.status_code == 200, r.text
    return r.json()


def _create_recurring(
    client: TestClient,
    headers: dict[str, str],
    due: date,
    recurrence: dict = WEEKLY,
    title: str = "Water the plants",
    **fields: object,
) -> dict:
    return _create_task(
        client,
        headers,
        title,
        due_date=due.isoformat(),
        recurrence=recurrence,
        **fields,
    )


def _patch(
    client: TestClient, headers: dict[str, str], task_id: str, **fields: object
) -> httpx.Response:
    return client.patch(f"{API}/tasks/{task_id}", headers=headers, json=fields)


def _complete(client: TestClient, headers: dict[str, str], task_id: str) -> dict:
    r = _patch(client, headers, task_id, status="done")
    assert r.status_code == 200, r.text
    return r.json()


def _tasks(client: TestClient, headers: dict[str, str], **params: object) -> list:
    r = client.get(f"{API}/tasks/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _open_occurrence(
    client: TestClient, headers: dict[str, str], title: str = "Water the plants"
) -> dict:
    """The one open task with this title, asserting there is exactly one."""
    matching = [
        t
        for t in _tasks(client, headers, status=["todo", "in_progress", "waiting"])
        if t["title"] == title and t["parent_id"] is None
    ]
    assert len(matching) == 1, matching
    return matching[0]


def _complete_and_get_next(
    client: TestClient, headers: dict[str, str], task_id: str
) -> dict:
    _complete(client, headers, task_id)
    return _open_occurrence(client, headers)


# --- Marking a task recurring -------------------------------------------------


def test_a_recurring_task_reports_its_recurrence(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(
        client,
        headers,
        date(2026, 3, 2),
        recurrence={"frequency": "every_n_days", "interval_days": 3},
    )

    expected = {"frequency": "every_n_days", "interval_days": 3}
    assert task["recurrence"] == expected
    r = client.get(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.json()["recurrence"] == expected
    assert _tasks(client, headers)[0]["recurrence"] == expected


def test_a_plain_task_reports_no_recurrence(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Once")
    assert task["recurrence"] is None


@pytest.mark.parametrize(
    "recurrence",
    [
        {"frequency": "every_n_days"},
        {"frequency": "every_n_days", "interval_days": 0},
        {"frequency": "weekly", "interval_days": 3},
        {"frequency": "yearly"},
    ],
)
def test_a_malformed_recurrence_is_rejected(
    client: TestClient, db: Session, recurrence: dict
) -> None:
    headers = _headers_for_new_user(client, db)
    r = client.post(
        f"{API}/tasks/",
        headers=headers,
        json={"title": "Bad", "due_date": "2026-03-02", "recurrence": recurrence},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(("days", "accepted"), [(1, False), (2, True)])
def test_every_n_days_starts_at_two_days(
    client: TestClient, db: Session, days: int, accepted: bool
) -> None:
    # Every one day is the daily rule spelt a second way; one rule has one
    # spelling, so the shortest "every N days" is two.
    headers = _headers_for_new_user(client, db)
    recurrence = {"frequency": "every_n_days", "interval_days": days}

    created = client.post(
        f"{API}/tasks/",
        headers=headers,
        json={"title": "Created", "due_date": "2026-03-02", "recurrence": recurrence},
    )
    task = _create_task(client, headers, "Updated", due_date="2026-03-02")
    updated = _patch(client, headers, task["id"], recurrence=recurrence)

    assert (created.status_code == 200) is accepted, created.text
    assert (updated.status_code == 200) is accepted, updated.text


@pytest.mark.parametrize(("days", "accepted"), [(1, False), (2, True)])
def test_a_bot_user_is_held_to_the_same_minimum(
    client: TestClient, db: Session, days: int, accepted: bool
) -> None:
    headers = create_user_headers(client, db)
    project = create_project(client, headers)
    bot = issue_bot_headers(
        client,
        headers,
        project_ids=[project],
        permissions={"read_tasks": True, "create_tasks": True},
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "By the bot",
            "project_id": project,
            "due_date": "2026-03-02",
            "recurrence": {"frequency": "every_n_days", "interval_days": days},
        },
    )

    assert (r.status_code == 200) is accepted, r.text


def test_the_minimum_is_published_in_the_api_schema(client: TestClient) -> None:
    # The web client reads the minimum from here rather than restating it.
    schema = client.get(f"{API}/openapi.json").json()
    interval = schema["components"]["schemas"]["Recurrence"]["properties"][
        "interval_days"
    ]
    assert {"type": "integer", "minimum": 2} in interval["anyOf"]


def test_a_task_cannot_recur_without_a_due_date(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.post(
        f"{API}/tasks/",
        headers=headers,
        json={"title": "Undated", "recurrence": WEEKLY},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "A recurring task needs a due date"

    plain = _create_task(client, headers, "Undated")
    r = _patch(client, headers, plain["id"], recurrence=WEEKLY)
    assert r.status_code == 400
    assert r.json()["detail"] == "A recurring task needs a due date"

    recurring = _create_recurring(client, headers, date(2026, 3, 2))
    r = _patch(
        client,
        headers,
        recurring["id"],
        due_date=None,
        due_date_scope="this_occurrence",
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "A recurring task needs a due date"


def test_a_subtask_cannot_recur(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")

    r = client.post(
        f"{API}/tasks/",
        headers=headers,
        json={
            "title": "Child",
            "parent_id": root["id"],
            "due_date": "2026-03-02",
            "recurrence": WEEKLY,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Only a task at the top of its tree can recur"

    child = _create_task(
        client, headers, "Child", parent_id=root["id"], due_date="2026-03-02"
    )
    r = _patch(client, headers, child["id"], recurrence=WEEKLY)
    assert r.status_code == 400


def test_an_existing_task_can_be_made_recurring(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Water the plants", due_date="2026-03-02")

    r = _patch(client, headers, task["id"], recurrence=WEEKLY)
    assert r.status_code == 200, r.text
    assert r.json()["recurrence"] == {"frequency": "weekly", "interval_days": None}

    successor = _complete_and_get_next(client, headers, task["id"])
    assert successor["due_date"] == "2026-03-09"


def test_a_task_stops_recurring_when_its_recurrence_is_cleared(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(client, headers, task["id"], recurrence=None)
    assert r.status_code == 200, r.text
    assert r.json()["recurrence"] is None

    _complete(client, headers, task["id"])
    assert _tasks(client, headers, status=["todo", "in_progress", "waiting"]) == []


def test_a_completed_task_cannot_change_how_it_recurs(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    _complete(client, headers, task["id"])

    r = _patch(client, headers, task["id"], recurrence={"frequency": "daily"})
    assert r.status_code == 400

    # Sending the rule it already has is not a change.
    r = _patch(client, headers, task["id"], recurrence=WEEKLY, title="Renamed")
    assert r.status_code == 200, r.text


def test_changing_the_rule_restarts_the_schedule_from_this_occurrence(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    second = _complete_and_get_next(client, headers, task["id"])
    assert second["due_date"] == "2026-03-09"

    r = _patch(client, headers, second["id"], recurrence={"frequency": "daily"})
    assert r.status_code == 200, r.text

    third = _complete_and_get_next(client, headers, second["id"])
    assert third["due_date"] == "2026-03-10"
    assert third["recurrence"] == {"frequency": "daily", "interval_days": None}


# --- Completing an occurrence -------------------------------------------------


@pytest.mark.parametrize(
    ("recurrence", "start", "expected"),
    [
        ({"frequency": "daily"}, date(2026, 3, 2), ["2026-03-03", "2026-03-04"]),
        ({"frequency": "weekly"}, date(2026, 3, 2), ["2026-03-09", "2026-03-16"]),
        (
            {"frequency": "every_n_days", "interval_days": 10},
            date(2026, 3, 2),
            ["2026-03-12", "2026-03-22"],
        ),
        # Counted on the calendar from the schedule, so a short month does not
        # pull every later occurrence back to its last day.
        ({"frequency": "monthly"}, date(2026, 1, 31), ["2026-02-28", "2026-03-31"]),
        ({"frequency": "monthly"}, date(2026, 11, 15), ["2026-12-15", "2027-01-15"]),
    ],
    ids=["daily", "weekly", "every-10-days", "monthly-month-end", "monthly-new-year"],
)
def test_each_interval_type_schedules_the_next_occurrences(
    client: TestClient,
    db: Session,
    recurrence: dict,
    start: date,
    expected: list[str],
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, start, recurrence=recurrence)

    second = _complete_and_get_next(client, headers, task["id"])
    third = _complete_and_get_next(client, headers, second["id"])

    assert [second["due_date"], third["due_date"]] == expected


def test_completing_an_occurrence_creates_a_new_task_and_keeps_the_old_one_completed(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))

    completed = _complete(client, headers, task["id"])
    assert completed["status"] == "done"
    assert completed["due_date"] == "2026-03-02"

    successor = _open_occurrence(client, headers)
    assert successor["id"] != task["id"]
    assert successor["status"] == "todo"

    r = client.get(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.json()["status"] == "done"


def test_the_next_occurrence_copies_the_task_fields(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    me = client.get(f"{API}/users/me", headers=headers).json()["id"]
    project = client.post(
        f"{API}/projects/", headers=headers, json={"name": "Home"}
    ).json()
    task = _create_recurring(
        client,
        headers,
        date(2026, 3, 2),
        description="Both balconies",
        priority="P2",
        assignee_id=me,
        tags=["home", "chores"],
        project_id=project["id"],
    )

    successor = _complete_and_get_next(client, headers, task["id"])

    for field in (
        "title",
        "description",
        "priority",
        "assignee_id",
        "tags",
        "project_id",
        "recurrence",
    ):
        assert successor[field] == task[field], field


def test_the_next_occurrence_copies_the_subtask_tree_not_completed(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 9), title="Weekly review")
    inbox = _create_task(
        client,
        headers,
        "Clear the inbox",
        parent_id=task["id"],
        tags=["email"],
        due_date="2026-03-08",
    )
    _create_task(client, headers, "Archive threads", parent_id=inbox["id"])
    plan = _create_task(client, headers, "Plan the week", parent_id=task["id"])
    gone = _create_task(client, headers, "Dropped step", parent_id=task["id"])
    assert _patch(client, headers, plan["id"], status="done").status_code == 200
    r = client.delete(f"{API}/tasks/{gone['id']}", headers=headers)
    assert r.status_code == 200

    r = _patch(client, headers, task["id"], status="done", subtasks="complete")
    assert r.status_code == 200, r.text

    successor = _open_occurrence(client, headers, "Weekly review")
    by_title = {
        t["title"]: t
        for t in _tasks(client, headers, status=["todo", "in_progress", "waiting"])
    }
    assert set(by_title) == {
        "Weekly review",
        "Clear the inbox",
        "Archive threads",
        "Plan the week",
    }
    assert by_title["Clear the inbox"]["parent_id"] == successor["id"]
    assert by_title["Plan the week"]["parent_id"] == successor["id"]
    assert by_title["Archive threads"]["parent_id"] == by_title["Clear the inbox"]["id"]
    assert by_title["Clear the inbox"]["tags"] == ["email"]
    # A subtask keeps its distance from the occurrence's due date.
    assert by_title["Clear the inbox"]["due_date"] == "2026-03-15"
    assert by_title["Plan the week"]["due_date"] is None
    # Copies are not occurrences in their own right.
    assert by_title["Clear the inbox"]["recurrence"] is None

    # The completed occurrence keeps its own tree, untouched.
    old = {
        t["title"]: t
        for t in _tasks(client, headers, status=["done"])
        if t["id"] != task["id"]
    }
    assert old["Clear the inbox"]["parent_id"] == task["id"]


def test_leaving_subtasks_uncompleted_still_starts_the_next_tree_fresh(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    _create_task(client, headers, "Fill the can", parent_id=task["id"])

    r = _patch(client, headers, task["id"], status="done", subtasks="leave_uncompleted")
    assert r.status_code == 200, r.text

    open_titles = sorted(
        t["title"]
        for t in _tasks(client, headers, status=["todo", "in_progress", "waiting"])
    )
    assert open_titles == ["Fill the can", "Fill the can", "Water the plants"]


def test_comments_and_attachments_stay_with_the_completed_occurrence(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    r = client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=headers, json={"body": "Done"}
    )
    assert r.status_code == 200
    r = client.post(
        f"{API}/tasks/{task['id']}/attachments/",
        headers=headers,
        files={"file": ("photo.jpg", b"jpeg", "image/jpeg")},
    )
    assert r.status_code == 200

    successor = _complete_and_get_next(client, headers, task["id"])

    for task_id, expected in ((task["id"], 1), (successor["id"], 0)):
        comments = client.get(f"{API}/tasks/{task_id}/comments/", headers=headers)
        attachments = client.get(f"{API}/tasks/{task_id}/attachments/", headers=headers)
        assert comments.json()["count"] == expected
        assert attachments.json()["count"] == expected


def test_late_completion_keeps_to_the_schedule(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    due = date.today() - timedelta(days=17)
    task = _create_recurring(client, headers, due)

    successor = _complete_and_get_next(client, headers, task["id"])

    # From the due date, not from today — even though that is still overdue.
    assert successor["due_date"] == (due + timedelta(days=7)).isoformat()
    assert successor["due_date"] < date.today().isoformat()


def test_completing_a_completed_occurrence_again_creates_nothing(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    _complete(client, headers, task["id"])
    _complete(client, headers, task["id"])

    assert len(_tasks(client, headers)) == 2
    _open_occurrence(client, headers)


# --- At most one open occurrence ---------------------------------------------


def test_a_superseded_occurrence_cannot_be_reopened(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    _complete(client, headers, task["id"])

    r = _patch(client, headers, task["id"], status="todo")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "occurrence_superseded"

    assert _open_occurrence(client, headers)["due_date"] == "2026-03-09"


def test_the_latest_occurrence_can_be_reopened_once_its_successor_is_deleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    successor = _complete_and_get_next(client, headers, task["id"])

    r = client.delete(f"{API}/tasks/{successor['id']}", headers=headers)
    assert r.status_code == 200
    r = _patch(client, headers, task["id"], status="todo")
    assert r.status_code == 200, r.text

    # Completing it again lands on the same place in the schedule.
    again = _complete_and_get_next(client, headers, task["id"])
    assert again["id"] != successor["id"]
    assert again["due_date"] == "2026-03-09"


def test_the_database_refuses_a_second_open_occurrence(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    _complete(client, headers, task["id"])

    db.expire_all()
    stored = db.get(Task, uuid.UUID(task["id"]))
    assert stored is not None
    stored.status = TaskStatus.TODO
    db.add(stored)
    with pytest.raises(Exception, match="ix_task_one_open_occurrence"):
        db.commit()
    db.rollback()


def test_completion_and_the_next_occurrence_commit_together(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))

    def fail(**_kwargs: object) -> None:
        raise RuntimeError("storage fell over")

    monkeypatch.setattr(crud, "_stage_next_occurrence", fail)
    with pytest.raises(RuntimeError):
        _patch(client, headers, task["id"], status="done")
    monkeypatch.undo()

    remaining = _tasks(client, headers)
    assert [t["id"] for t in remaining] == [task["id"]]
    assert remaining[0]["status"] == "todo"


# --- Moving the due date of an open occurrence --------------------------------


def test_moving_an_open_occurrence_requires_a_scope(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(client, headers, task["id"], due_date="2026-03-04")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "due_date_scope_required"

    r = client.get(f"{API}/tasks/{task['id']}", headers=headers)
    assert r.json()["due_date"] == "2026-03-02"


def test_resending_the_same_due_date_needs_no_scope(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(client, headers, task["id"], due_date="2026-03-02", title="Renamed")
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("scope", ["this_occurrence", "this_and_following"])
def test_a_scope_is_refused_where_there_is_no_series_to_reschedule(
    client: TestClient, db: Session, scope: str
) -> None:
    headers = _headers_for_new_user(client, db)
    plain = _create_task(client, headers, "Once", due_date="2026-03-02")
    r = _patch(
        client, headers, plain["id"], due_date="2026-03-04", due_date_scope=scope
    )
    assert r.status_code == 400

    recurring = _create_recurring(client, headers, date(2026, 3, 2))
    r = _patch(client, headers, recurring["id"], title="No date", due_date_scope=scope)
    assert r.status_code == 400

    _complete(client, headers, recurring["id"])
    r = _patch(
        client, headers, recurring["id"], due_date="2026-03-03", due_date_scope=scope
    )
    assert r.status_code == 400


def test_a_completed_occurrence_moves_like_any_task(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_recurring(client, headers, date(2026, 3, 2))
    _complete(client, headers, task["id"])

    r = _patch(client, headers, task["id"], due_date="2026-03-01")
    assert r.status_code == 200, r.text
    assert _open_occurrence(client, headers)["due_date"] == "2026-03-09"


def test_only_this_occurrence_leaves_the_schedule_alone(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    first = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(
        client,
        headers,
        first["id"],
        due_date="2026-03-05",
        due_date_scope="this_occurrence",
    )
    assert r.status_code == 200, r.text
    assert r.json()["due_date"] == "2026-03-05"

    second = _complete_and_get_next(client, headers, first["id"])
    assert second["due_date"] == "2026-03-09"

    r = _patch(
        client,
        headers,
        second["id"],
        due_date="2026-03-11",
        due_date_scope="this_occurrence",
    )
    assert r.status_code == 200, r.text

    third = _complete_and_get_next(client, headers, second["id"])
    assert third["due_date"] == "2026-03-16"


def test_this_and_following_occurrences_shift_the_series(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    first = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(
        client,
        headers,
        first["id"],
        due_date="2026-03-05",
        due_date_scope="this_and_following",
    )
    assert r.status_code == 200, r.text
    assert r.json()["due_date"] == "2026-03-05"

    second = _complete_and_get_next(client, headers, first["id"])
    assert second["due_date"] == "2026-03-12"

    third = _complete_and_get_next(client, headers, second["id"])
    assert third["due_date"] == "2026-03-19"


@pytest.mark.parametrize(
    ("scope", "expected"),
    [("this_occurrence", "2026-03-09"), ("this_and_following", "2026-03-12")],
)
def test_the_scope_holds_when_the_whole_task_is_resent(
    client: TestClient, db: Session, scope: str, expected: str
) -> None:
    """An edit form sends every field back, the unchanged recurrence included."""
    headers = _headers_for_new_user(client, db)
    first = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(
        client,
        headers,
        first["id"],
        title=first["title"],
        tags=first["tags"],
        recurrence=first["recurrence"],
        due_date="2026-03-05",
        due_date_scope=scope,
    )
    assert r.status_code == 200, r.text

    assert _complete_and_get_next(client, headers, first["id"])["due_date"] == expected


def test_rescheduling_and_completing_in_one_request(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    first = _create_recurring(client, headers, date(2026, 3, 2))

    r = _patch(
        client,
        headers,
        first["id"],
        due_date="2026-03-04",
        due_date_scope="this_and_following",
        status="done",
    )
    assert r.status_code == 200, r.text

    assert _open_occurrence(client, headers)["due_date"] == "2026-03-11"
