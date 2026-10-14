"""
`whoami` (spec #252): answers exactly what `GET /caller` answers (spec #245,
#249), read over MCP instead of REST.

Exercised against `whoami_body` directly (#302) — a session and a `Caller`,
with no protocol in between; `tests/mcp/test_transport.py` keeps the handful
of end-to-end tests that cover the protocol itself, and one consolidated
test there (`test_tools_advertise_their_annotations`) covers every tool's
`tools/list` entry, this one included.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.whoami import whoami_body
from tests.utils.accounts import (
    READ_ONLY,
    create_archived_project,
    create_bot_user,
    create_project,
    create_user_headers,
    inbox_project_id,
    token_headers,
)
from tests.utils.mcp import bot_headers
from tests.utils.mcp_body import caller_for

API = settings.API_V1_STR


def test_whoami_answers_exactly_what_the_caller_endpoint_answers(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    permissions = {"read_tasks": True, "add_comments": True}
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=permissions, name="Agent"
    )

    rest = client.get(f"{API}/caller", headers=headers)
    assert rest.status_code == 200, rest.text

    assert whoami_body(db, caller_for(db, headers)) == rest.json()


def test_whoami_marks_the_inbox_among_the_scopes_projects(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    inbox_id = inbox_project_id(client, owner)
    work = create_project(client, owner, name="Work")
    headers = bot_headers(client, owner, project_ids=[inbox_id, work])

    result = whoami_body(db, caller_for(db, headers))
    inbox = next(p for p in result["projects"] if p["id"] == inbox_id)
    assert inbox["is_inbox"] is True
    assert [p["id"] for p in result["projects"]][0] == inbox_id


def test_whoami_reports_todays_date(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)
    result = whoami_body(db, caller_for(db, headers))
    assert result["today"] == date.today().isoformat()


def test_an_archived_project_is_absent_from_whoami(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    live = create_project(client, owner, name="Live")
    archived = create_archived_project(client, owner, "Shelved")
    headers = bot_headers(client, owner, project_ids=[live, archived])

    result = whoami_body(db, caller_for(db, headers))
    assert [p["id"] for p in result["projects"]] == [live]


def test_whoami_reports_a_scope_or_permission_change_without_recaching(
    client: TestClient, db: Session
) -> None:
    """
    Nothing about the caller is cached between calls (ADR-0012): a scope or a
    grant edited between two calls shows in the second, with no new session
    and no new token — resolving a fresh `Caller` from the same token, the
    way `open_caller` does on every call, is what makes that true, with no
    protocol session needed to demonstrate it.
    """
    owner = create_user_headers(client, db)
    first = create_project(client, owner, name="First")
    bot = create_bot_user(client, owner, project_ids=[first], permissions=READ_ONLY)
    headers = token_headers(client, owner, bot["id"])

    before = whoami_body(db, caller_for(db, headers))
    assert [p["id"] for p in before["projects"]] == [first]
    assert before["permissions"]["add_comments"] is False

    second = create_project(client, owner, name="Second")
    grown = {**READ_ONLY, "add_comments": True}
    r = client.patch(
        f"{API}/bot-users/{bot['id']}",
        headers=owner,
        json={"scope": {"project_ids": [first, second], "permissions": grown}},
    )
    assert r.status_code == 200, r.text

    after = whoami_body(db, caller_for(db, headers))
    assert {p["id"] for p in after["projects"]} == {first, second}
    assert after["permissions"]["add_comments"] is True
