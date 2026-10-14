"""
`list_tags` (spec #247, #254): the owner's whole tag vocabulary, narrowable
by a substring and never narrowed by the caller's own scope (ADR-0003).

Exercised against `list_tags_body` directly (#302) — see `test_whoami.py`'s
own module docstring for why, and where the protocol itself is still tested.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.mcp.tools.list_tags import list_tags_body
from tests.utils.accounts import (
    archive_project,
    create_project,
    create_task_record,
    create_user_headers,
)
from tests.utils.mcp import bot_headers
from tests.utils.mcp_body import caller_for


def test_lists_tags_with_task_counts(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "One", project_id=project_id, tags=["ci"])
    create_task_record(client, owner, "Two", project_id=project_id, tags=["ci"])
    create_task_record(client, owner, "Three", project_id=project_id, tags=["docs"])
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = list_tags_body(db, caller, q=None, limit=50)
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
    caller = caller_for(db, headers)

    # "tinu" is in the middle of "continuous", never at its start: a prefix
    # match (the REST route's own `q`) would miss it, a substring match finds
    # it (spec #254).
    result = list_tags_body(db, caller, q="tinu", limit=50)
    assert [tag["name"] for tag in result["tags"]] == ["continuous"]


def test_limit_truncates_and_names_q_to_narrow_with(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    for name in ["alpha", "beta", "gamma"]:
        create_task_record(client, owner, name, project_id=project_id, tags=[name])
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = list_tags_body(db, caller, q=None, limit=2)
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
    caller = caller_for(db, headers)

    result = list_tags_body(db, caller, q=None, limit=50)
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
    caller = caller_for(db, headers)

    result = list_tags_body(db, caller, q=None, limit=50)
    assert {tag["name"] for tag in result["tags"]} == {"a", "b"}


def test_archived_tasks_are_counted_apart(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Shelved")
    create_task_record(client, owner, "Task", project_id=project_id, tags=["ci"])
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    result = list_tags_body(db, caller, q=None, limit=50)
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
    caller = caller_for(db, headers)

    result = list_tags_body(db, caller, q=None, limit=50)
    assert [tag["name"] for tag in result["tags"]] == ["ci"]
