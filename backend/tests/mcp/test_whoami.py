"""
`whoami`, the one tool this ticket builds (spec #252): answers exactly what
`GET /caller` answers (spec #245, #249), read over MCP instead of REST.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    READ_ONLY,
    create_archived_project,
    create_bot_user,
    create_project,
    create_user_headers,
    inbox_project_id,
    token_headers,
)
from tests.utils.mcp import bot_headers, call_tool, list_tools, start_session

API = settings.API_V1_STR


def test_tools_list_advertises_whoami_read_only(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    whoami = next(t for t in tools if t["name"] == "whoami")
    assert whoami["description"]
    assert whoami["annotations"]["readOnlyHint"] is True


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

    assert call_tool(client, headers, "whoami") == rest.json()


def test_whoami_marks_the_inbox_among_the_scopes_projects(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    inbox_id = inbox_project_id(client, owner)
    work = create_project(client, owner, name="Work")
    headers = bot_headers(client, owner, project_ids=[inbox_id, work])

    result = call_tool(client, headers, "whoami")
    inbox = next(p for p in result["projects"] if p["id"] == inbox_id)
    assert inbox["is_inbox"] is True
    assert [p["id"] for p in result["projects"]][0] == inbox_id


def test_whoami_reports_todays_date(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)
    assert call_tool(client, headers, "whoami")["today"] == date.today().isoformat()


def test_an_archived_project_is_absent_from_whoami(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    live = create_project(client, owner, name="Live")
    archived = create_archived_project(client, owner, "Shelved")
    headers = bot_headers(client, owner, project_ids=[live, archived])

    result = call_tool(client, headers, "whoami")
    assert [p["id"] for p in result["projects"]] == [live]


def test_whoami_reports_a_scope_or_permission_change_without_a_new_session(
    client: TestClient, db: Session
) -> None:
    """
    Nothing about the caller is cached between calls (spec #252): a scope or
    a grant edited between two calls on the *same* MCP session shows in the
    second, with no new session and no new token.
    """
    owner = create_user_headers(client, db)
    first = create_project(client, owner, name="First")
    bot = create_bot_user(client, owner, project_ids=[first], permissions=READ_ONLY)
    headers = token_headers(client, owner, bot["id"])
    session = start_session(client, headers)

    before = call_tool(client, headers, "whoami", session=session)
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

    after = call_tool(client, headers, "whoami", session=session)
    assert {p["id"] for p in after["projects"]} == {first, second}
    assert after["permissions"]["add_comments"] is True
