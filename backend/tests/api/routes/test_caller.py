"""
`GET /caller`: what a human session and a bot token each learn about
themselves — who they are, whose data they reach, what they may do there, and
today's date (spec #245, issue #249).
"""

from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    READ_ONLY,
    create_archived_project,
    create_bot_user,
    create_project,
    create_project_record,
    create_task,
    create_user_headers,
    inbox_project_id,
    token_headers,
)
from tests.utils.user import create_random_user, give_passkey, sign_in

API = settings.API_V1_STR

Headers = dict[str, str]


def _caller(client: TestClient, headers: Headers) -> Any:
    r = client.get(f"{API}/caller", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# --- A human session -----------------------------------------------------------


def test_a_human_session_sees_itself_as_the_actor_with_every_permission_and_no_projects(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db, full_name="Alex Doe")
    headers = sign_in(client, give_passkey(db, user))

    body = _caller(client, headers)
    assert body["actor"] == {
        "kind": "user",
        "id": str(user.id),
        "name": "Alex Doe",
    }
    assert body["owner_id"] == str(user.id)
    assert body["permissions"] == {
        "create_tasks": True,
        "read_tasks": True,
        "update_tasks": True,
        "delete_tasks": True,
        "add_comments": True,
        "create_tags": True,
        "read_activity": True,
    }
    assert body["projects"] is None


def test_a_human_with_no_full_name_is_named_by_their_email(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    headers = sign_in(client, give_passkey(db, user))

    body = _caller(client, headers)
    assert body["actor"]["name"] == user.email


def test_today_is_the_servers_date(client: TestClient, db: Session) -> None:
    headers = create_user_headers(client, db)
    assert _caller(client, headers)["today"] == date.today().isoformat()


# --- A bot user ------------------------------------------------------------


def test_a_bot_user_sees_its_own_identity_its_owners_id_and_exactly_its_grants(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    owner_id = _caller(client, owner)["actor"]["id"]
    project_id = create_project(client, owner)
    permissions = {"read_tasks": True, "add_comments": True}
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=permissions, name="Agent"
    )
    bot_headers = token_headers(client, owner, bot["id"])

    body = _caller(client, bot_headers)
    assert body["actor"] == {"kind": "bot_user", "id": bot["id"], "name": "Agent"}
    assert body["owner_id"] == owner_id
    assert body["permissions"] == {
        "create_tasks": False,
        "read_tasks": True,
        "update_tasks": False,
        "delete_tasks": False,
        "add_comments": True,
        "create_tags": False,
        "read_activity": False,
    }


def test_a_bot_users_read_activity_grant_is_reported_true_when_granted(
    client: TestClient, db: Session
) -> None:
    """
    `read_activity` is false by default (previous test) and reads back true
    once the owner grants it — the only thing this slice makes happen; the
    grant opens nothing on the log itself until #251.
    """
    owner = create_user_headers(client, db)
    bot = create_bot_user(
        client,
        owner,
        project_ids=[],
        permissions={"read_activity": True},
        name="Reporter",
    )
    bot_headers = token_headers(client, owner, bot["id"])

    body = _caller(client, bot_headers)
    assert body["permissions"]["read_activity"] is True


def test_a_bot_users_projects_are_its_scope_inbox_first_then_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    inbox_id = inbox_project_id(client, owner)
    zebra = create_project(client, owner, name="Zebra")
    apple = create_project(client, owner, name="apple")  # lowercase, sorts with Apple
    bot_headers = token_headers(
        client,
        owner,
        create_bot_user(
            client,
            owner,
            project_ids=[zebra, inbox_id, apple],
            permissions=READ_ONLY,
        )["id"],
    )

    projects = _caller(client, bot_headers)["projects"]
    assert [p["id"] for p in projects] == [inbox_id, apple, zebra]
    assert projects[0]["is_inbox"] is True
    assert projects[1]["is_inbox"] is False
    assert projects[2]["is_inbox"] is False


def test_an_archived_project_is_absent_from_a_bot_users_projects(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    live = create_project(client, owner, name="Live")
    archived = create_archived_project(client, owner, "Shelved")
    bot_headers = token_headers(
        client,
        owner,
        create_bot_user(
            client, owner, project_ids=[live, archived], permissions=READ_ONLY
        )["id"],
    )

    projects = _caller(client, bot_headers)["projects"]
    assert [p["id"] for p in projects] == [live]


def test_a_scope_change_shows_up_on_the_next_call_without_a_new_token(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    first = create_project(client, owner, name="First")
    bot = create_bot_user(client, owner, project_ids=[first], permissions=READ_ONLY)
    bot_headers = token_headers(client, owner, bot["id"])
    assert [p["id"] for p in _caller(client, bot_headers)["projects"]] == [first]

    second = create_project(client, owner, name="Second")
    r = client.patch(
        f"{API}/bot-users/{bot['id']}",
        headers=owner,
        json={"scope": {"project_ids": [first, second], "permissions": READ_ONLY}},
    )
    assert r.status_code == 200, r.text

    projects = _caller(client, bot_headers)["projects"]
    assert {p["id"] for p in projects} == {first, second}


def test_a_projects_open_task_count_matches_the_project_lists(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project = create_project_record(client, owner, "Busy")
    create_task(client, owner, project_id=project["id"], title="One")
    create_task(client, owner, project_id=project["id"], title="Two")
    done = create_task(client, owner, project_id=project["id"], title="Done")
    client.patch(f"{API}/tasks/{done}", headers=owner, json={"status": "done"})
    bot_headers = token_headers(
        client,
        owner,
        create_bot_user(
            client, owner, project_ids=[project["id"]], permissions=READ_ONLY
        )["id"],
    )

    listed = next(
        p
        for p in client.get(f"{API}/projects/", headers=owner).json()["data"]
        if p["id"] == project["id"]
    )
    caller_project = next(
        p for p in _caller(client, bot_headers)["projects"] if p["id"] == project["id"]
    )
    assert caller_project["open_tasks"] == listed["open_count"] == 2


def test_a_bot_user_learns_nothing_about_other_bot_users_or_projects_outside_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, name="InScope")
    outside = create_project(client, owner, name="Outside")
    create_bot_user(client, owner, project_ids=[outside], permissions=READ_ONLY)
    bot_headers = token_headers(
        client,
        owner,
        create_bot_user(
            client, owner, project_ids=[in_scope], permissions=READ_ONLY, name="Scoped"
        )["id"],
    )

    body = _caller(client, bot_headers)
    assert [p["id"] for p in body["projects"]] == [in_scope]


# --- Refusals --------------------------------------------------------------


def test_no_credentials_is_unauthorized(client: TestClient) -> None:
    r = client.get(f"{API}/caller")
    assert r.status_code == 401


def test_a_revoked_expired_or_deleted_bot_users_token_is_the_same_401(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)

    revoked_bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=READ_ONLY, name="Revoked"
    )
    revoked_headers = token_headers(client, owner, revoked_bot["id"])
    r = client.delete(f"{API}/bot-users/{revoked_bot['id']}/token", headers=owner)
    assert r.status_code == 200, r.text

    deleted_bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=READ_ONLY, name="Deleted"
    )
    deleted_headers = token_headers(client, owner, deleted_bot["id"])
    r = client.delete(f"{API}/bot-users/{deleted_bot['id']}", headers=owner)
    assert r.status_code == 200, r.text

    unknown = {"Authorization": "Bearer taskly_bot_" + "x" * 43}

    for headers in (revoked_headers, deleted_headers, unknown):
        r = client.get(f"{API}/caller", headers=headers)
        assert r.status_code == 401


def test_users_me_is_unchanged_and_still_refuses_a_bot_token(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot_headers = token_headers(
        client,
        owner,
        create_bot_user(client, owner, project_ids=[], permissions=READ_ONLY)["id"],
    )

    r = client.get(f"{API}/users/me", headers=bot_headers)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "human_only"


def test_the_call_writes_nothing_to_the_activity_log(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot_headers = token_headers(
        client,
        owner,
        create_bot_user(
            client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
        )["id"],
    )

    before = client.get(f"{API}/activity-log/", headers=owner).json()["count"]
    _caller(client, bot_headers)
    _caller(client, owner)
    after = client.get(f"{API}/activity-log/", headers=owner).json()["count"]
    assert after == before
