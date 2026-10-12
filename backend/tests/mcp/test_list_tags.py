"""
`list_tags` (spec #247, #254): the owner's whole tag vocabulary, narrowable
by a substring and never narrowed by the caller's own scope (ADR-0003).
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    archive_project,
    create_project,
    create_task_record,
    create_user_headers,
)
from tests.utils.mcp import bot_headers, call_tool, list_tools

API = settings.API_V1_STR


def test_tools_list_advertises_list_tags_read_only(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    headers = bot_headers(client, owner)

    tools = list_tools(client, headers)
    list_tags = next(t for t in tools if t["name"] == "list_tags")
    assert list_tags["description"]
    assert list_tags["annotations"]["readOnlyHint"] is True


def test_lists_tags_with_task_counts(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "One", project_id=project_id, tags=["ci"])
    create_task_record(client, owner, "Two", project_id=project_id, tags=["ci"])
    create_task_record(client, owner, "Three", project_id=project_id, tags=["docs"])
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(client, headers, "list_tags", {})
    by_name = {tag["name"]: tag for tag in result["tags"]}
    assert by_name["ci"]["task_count"] == 2
    assert by_name["docs"]["task_count"] == 1
    assert result["count"] == 2


def test_narrows_by_a_substring_anywhere_in_the_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "One", project_id=project_id, tags=["continuous"])
    create_task_record(client, owner, "Two", project_id=project_id, tags=["docs"])
    headers = bot_headers(client, owner, project_ids=[project_id])

    # "tinu" is in the middle of "continuous", never at its start: a prefix
    # match (the REST route's own `q`) would miss it, a substring match finds
    # it (spec #254).
    result = call_tool(client, headers, "list_tags", {"q": "tinu"})
    assert [tag["name"] for tag in result["tags"]] == ["continuous"]


def test_limit_truncates_and_names_q_to_narrow_with(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    for name in ["alpha", "beta", "gamma"]:
        create_task_record(client, owner, name, project_id=project_id, tags=[name])
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(client, headers, "list_tags", {"limit": 2})
    assert result["count"] == 3
    assert len(result["tags"]) == 2
    assert result["truncated"] is True
    assert result["narrow_with"] == "q"


def test_a_complete_result_is_not_marked_truncated(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "One", project_id=project_id, tags=["ci"])
    headers = bot_headers(client, owner, project_ids=[project_id])

    result = call_tool(client, headers, "list_tags", {})
    assert result["count"] == 1
    assert "truncated" not in result


def test_not_narrowed_by_the_bot_users_own_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, name="In scope")
    outside = create_project(client, owner, name="Outside")
    create_task_record(client, owner, "In scope task", project_id=in_scope, tags=["a"])
    create_task_record(client, owner, "Outside task", project_id=outside, tags=["b"])
    headers = bot_headers(client, owner, project_ids=[in_scope])

    result = call_tool(client, headers, "list_tags", {})
    assert {tag["name"] for tag in result["tags"]} == {"a", "b"}


def test_archived_tasks_are_counted_apart(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Shelved")
    create_task_record(client, owner, "Task", project_id=project_id, tags=["ci"])
    headers = bot_headers(client, owner, project_ids=[project_id])

    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    result = call_tool(client, headers, "list_tags", {})
    [tag] = result["tags"]
    assert tag["task_count"] == 0
    assert tag["archived_task_count"] == 1


def test_no_permission_is_needed_to_read_tags(client: TestClient, db: Session) -> None:
    """
    Reading tags needs no grant at all (`app.models.BotPermissions`'s own
    docstring): a bot user with no permissions whatsoever still reads the
    owner's vocabulary.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Task", project_id=project_id, tags=["ci"])
    headers = bot_headers(client, owner, project_ids=[], permissions={})

    result = call_tool(client, headers, "list_tags", {})
    assert [tag["name"] for tag in result["tags"]] == ["ci"]
