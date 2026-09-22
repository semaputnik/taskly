import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
from tests.utils.utils import random_email, random_lower_string

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)


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


def _me(client: TestClient, headers: dict[str, str]) -> str:
    return client.get(f"{settings.API_V1_STR}/users/me", headers=headers).json()["id"]


def _titles(client: TestClient, headers: dict[str, str], **query: object) -> list[str]:
    r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers, params=query)
    assert r.status_code == 200, r.text
    return [task["title"] for task in r.json()["data"]]


def test_filter_by_project_includes_subtasks_of_that_project(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    work_id = _create_project(client, headers, "Work")

    root = _create_task(client, headers, "At work", project_id=work_id)
    # A subtask stores no project of its own: it has to be found through its
    # root ancestor.
    _create_task(client, headers, "Under it", parent_id=root["id"])
    _create_task(client, headers, "In the Inbox")

    assert sorted(_titles(client, headers, project_id=work_id)) == [
        "At work",
        "Under it",
    ]


def test_filter_by_another_users_project_is_refused(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    project_id = _create_project(client, headers_b, "B's project")

    r = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers_a,
        params={"project_id": project_id},
    )
    assert r.status_code == 404


def test_filter_by_assignee_and_by_being_unassigned(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    user_id = _me(client, headers)

    _create_task(client, headers, "Mine", assignee_id=user_id)
    _create_task(client, headers, "Nobody's")

    assert _titles(client, headers, assignee_id=user_id) == ["Mine"]
    assert _titles(client, headers, unassigned=True) == ["Nobody's"]


def test_asking_for_an_assignee_and_unassigned_at_once_is_refused(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    user_id = _me(client, headers)

    r = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        params={"assignee_id": user_id, "unassigned": True},
    )
    assert r.status_code == 422


def test_filter_by_tag(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    _create_task(client, headers, "Tagged", tags=["urgent", "home"])
    _create_task(client, headers, "Also tagged", tags=["home"])
    _create_task(client, headers, "Untagged")

    assert _titles(client, headers, tag="urgent") == ["Tagged"]
    assert sorted(_titles(client, headers, tag="home")) == ["Also tagged", "Tagged"]
    assert _titles(client, headers, tag="nobody-uses-this") == []


def test_a_tag_filter_does_not_reach_another_users_tasks(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)

    _create_task(client, headers_a, "A's tagged task", tags=["shared-name"])
    _create_task(client, headers_b, "B's tagged task", tags=["shared-name"])

    assert _titles(client, headers_b, tag="shared-name") == ["B's tagged task"]


def test_filter_by_priority_treats_unset_as_p4(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    _create_task(client, headers, "Top", priority="P1")
    _create_task(client, headers, "Bottom", priority="P4")
    _create_task(client, headers, "Unset")

    assert _titles(client, headers, priority="P1") == ["Top"]
    # Unset behaves as P4 everywhere else, so it has to answer to a P4 filter.
    assert sorted(_titles(client, headers, priority="P4")) == ["Bottom", "Unset"]


OPEN = ["todo", "in_progress", "waiting"]


def test_filter_by_one_or_more_statuses(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    for title, status in (
        ("Planned", "todo"),
        ("Started", "in_progress"),
        ("Parked", "waiting"),
        ("Finished", "done"),
    ):
        task = _create_task(client, headers, title)
        r = client.patch(
            f"{settings.API_V1_STR}/tasks/{task['id']}",
            headers=headers,
            json={"status": status},
        )
        assert r.status_code == 200, r.text

    assert _titles(client, headers, status="done") == ["Finished"]
    assert _titles(client, headers, status="waiting") == ["Parked"]
    assert sorted(_titles(client, headers, status=["todo", "in_progress"])) == [
        "Planned",
        "Started",
    ]
    assert sorted(_titles(client, headers, status=OPEN)) == [
        "Parked",
        "Planned",
        "Started",
    ]
    # No status asked for is every status.
    assert len(_titles(client, headers)) == 4


def test_an_unknown_status_is_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    r = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        params={"status": "completed"},
    )
    assert r.status_code == 422


def test_filter_by_a_due_date_range(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    _create_task(client, headers, "Yesterday", due_date=str(YESTERDAY))
    _create_task(client, headers, "Today", due_date=str(TODAY))
    _create_task(client, headers, "Next week", due_date=str(NEXT_WEEK))
    _create_task(client, headers, "Someday")

    # The range takes both ends with it.
    assert sorted(_titles(client, headers, due_from=str(TODAY), due_to=str(TODAY))) == [
        "Today"
    ]
    assert sorted(
        _titles(client, headers, due_from=str(YESTERDAY), due_to=str(TODAY))
    ) == ["Today", "Yesterday"]
    assert _titles(client, headers, due_to=str(YESTERDAY)) == ["Yesterday"]


def test_filter_for_overdue_tasks(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    _create_task(client, headers, "Late", due_date=str(YESTERDAY))
    _create_task(client, headers, "Due tomorrow", due_date=str(TOMORROW))
    _create_task(client, headers, "No due date")
    done = _create_task(client, headers, "Late but done", due_date=str(YESTERDAY))
    client.patch(
        f"{settings.API_V1_STR}/tasks/{done['id']}",
        headers=headers,
        json={"status": "done"},
    )

    parked = _create_task(client, headers, "Late and waiting", due_date=str(YESTERDAY))
    client.patch(
        f"{settings.API_V1_STR}/tasks/{parked['id']}",
        headers=headers,
        json={"status": "waiting"},
    )

    # Overdue is open work past its date: a done task is never late, and a
    # waiting one still is. Which open statuses to show is the status filter's
    # call.
    assert sorted(_titles(client, headers, overdue=True)) == [
        "Late",
        "Late and waiting",
    ]
    assert _titles(client, headers, overdue=True, status="waiting") == [
        "Late and waiting"
    ]


def test_filters_combine_with_and(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    work_id = _create_project(client, headers, "Work")

    wanted = _create_task(
        client,
        headers,
        "All three",
        project_id=work_id,
        tags=["urgent"],
        due_date=str(TOMORROW),
    )
    # Each of these matches two of the three filters and must still be left out.
    _create_task(
        client, headers, "Wrong project", tags=["urgent"], due_date=str(TOMORROW)
    )
    _create_task(
        client, headers, "Wrong tag", project_id=work_id, due_date=str(TOMORROW)
    )
    _create_task(client, headers, "Wrong date", project_id=work_id, tags=["urgent"])

    titles = _titles(
        client,
        headers,
        project_id=work_id,
        tag="urgent",
        due_from=str(TODAY),
        due_to=str(NEXT_WEEK),
    )
    assert titles == [wanted["title"]]


def test_sort_by_due_date_both_ways(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    _create_task(client, headers, "Later", due_date=str(NEXT_WEEK))
    _create_task(client, headers, "Sooner", due_date=str(TODAY))
    _create_task(client, headers, "Whenever")

    # No due date is not a date at either end: those tasks go last either way.
    assert _titles(client, headers, sort="due_date") == [
        "Sooner",
        "Later",
        "Whenever",
    ]
    assert _titles(client, headers, sort="due_date", order="desc") == [
        "Later",
        "Sooner",
        "Whenever",
    ]


def test_sort_by_priority_both_ways(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    _create_task(client, headers, "Middle", priority="P2")
    _create_task(client, headers, "Unset")
    _create_task(client, headers, "Top", priority="P1")

    assert _titles(client, headers, sort="priority") == ["Top", "Middle", "Unset"]
    assert _titles(client, headers, sort="priority", order="desc") == [
        "Unset",
        "Middle",
        "Top",
    ]


def test_sort_by_creation_date_is_newest_first(client: TestClient, db: Session) -> None:
    """
    Each order has a natural direction, and for the created order it is
    newest first: asking for it without naming a direction means what a
    person would expect it to mean.
    """
    headers = _headers_for_new_user(client, db)
    for title in ("Oldest", "Middle", "Newest"):
        _create_task(client, headers, title)

    assert _titles(client, headers, sort="created_at") == [
        "Newest",
        "Middle",
        "Oldest",
    ]
    assert _titles(client, headers, sort="created_at", order="asc") == [
        "Oldest",
        "Middle",
        "Newest",
    ]


def test_the_other_orders_keep_the_direction_they_always_had(
    client: TestClient, db: Session
) -> None:
    """
    Due date and priority still lead with soonest and P1 when no direction
    is named, so URLs written before the created order keep their meaning.
    """
    headers = _headers_for_new_user(client, db)
    _create_task(client, headers, "Later", due_date=str(TODAY + timedelta(days=2)))
    _create_task(client, headers, "Sooner", due_date=str(TODAY))
    _create_task(client, headers, "Low", priority="P3")
    _create_task(client, headers, "High", priority="P1")

    assert _titles(client, headers, sort="due_date")[:2] == ["Sooner", "Later"]
    assert _titles(client, headers, sort="priority")[:1] == ["High"]


def test_the_created_order_pages_without_repeating_or_skipping(
    client: TestClient, db: Session
) -> None:
    """
    Creation timestamps can tie, so the order needs a tiebreak of its own:
    without one, two pages of the same list can show the same task twice and
    never show another.
    """
    headers = _headers_for_new_user(client, db)
    for n in range(6):
        _create_task(client, headers, f"T{n}")

    seen: list[str] = []
    for skip in (0, 2, 4):
        r = client.get(
            f"{settings.API_V1_STR}/tasks/",
            headers=headers,
            params={"sort": "created_at", "skip": skip, "limit": 2},
        )
        assert r.status_code == 200, r.text
        seen += [task["title"] for task in r.json()["data"]]

    assert sorted(seen) == [f"T{n}" for n in range(6)]


def test_sorting_and_filtering_work_together_with_pagination(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    for day, title in enumerate(["First", "Second", "Third"]):
        _create_task(
            client,
            headers,
            title,
            tags=["paged"],
            due_date=str(TODAY + timedelta(days=day)),
        )
    _create_task(client, headers, "Not in the filter")

    r = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        params={"tag": "paged", "sort": "due_date", "skip": 1, "limit": 1},
    )
    assert r.status_code == 200
    # The count is what the filter matches, not what the page holds.
    assert r.json()["count"] == 3
    assert [task["title"] for task in r.json()["data"]] == ["Second"]


def test_deleted_tasks_never_show_up_in_a_filtered_list(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    doomed = _create_task(client, headers, "Doomed", tags=["urgent"], priority="P1")
    _create_task(client, headers, "Survivor", tags=["urgent"], priority="P1")

    client.delete(f"{settings.API_V1_STR}/tasks/{doomed['id']}", headers=headers)

    assert _titles(client, headers, tag="urgent") == ["Survivor"]
    assert _titles(client, headers, priority="P1") == ["Survivor"]
    assert _titles(client, headers, sort="priority") == ["Survivor"]


def test_nonsense_paging_is_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    for params in ({"limit": -1}, {"skip": -1}, {"limit": 0}):
        r = client.get(f"{settings.API_V1_STR}/tasks/", headers=headers, params=params)
        assert r.status_code == 422, params


def test_an_unknown_sort_field_is_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(
        f"{settings.API_V1_STR}/tasks/", headers=headers, params={"sort": "title"}
    )
    assert r.status_code == 422


def test_filters_do_not_reach_another_users_tasks(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    _create_task(client, headers_a, "A's task", priority="P1")

    assert _titles(client, headers_b, priority="P1") == []
    assert _titles(client, headers_b, sort="priority") == []


def test_an_unknown_project_filter_is_refused(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)

    r = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        params={"project_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


def test_filter_by_parent_lists_only_its_direct_subtasks(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    child = _create_task(client, headers, "Child", parent_id=root["id"])
    _create_task(client, headers, "Grandchild", parent_id=child["id"])
    _create_task(client, headers, "Unrelated")

    assert _titles(client, headers, parent_id=root["id"]) == ["Child"]
    assert _titles(client, headers, parent_id=child["id"]) == ["Grandchild"]


def test_filter_by_another_users_task_as_parent_is_refused(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    parent = _create_task(client, headers_b, "B's task")
    _create_task(client, headers_b, "B's subtask", parent_id=parent["id"])

    r = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers_a,
        params={"parent_id": parent["id"]},
    )
    assert r.status_code == 404
