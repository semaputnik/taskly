"""
`search_tasks` (spec #247, #253): the task list's own narrowing (F-06), read
over MCP.

Exercised against `search_tasks_body` directly (#302) — see
`test_whoami.py`'s own module docstring for why, and where the protocol
itself is still tested. `test_a_null_argument_is_refused_rather_than_treated_as_absent`
is the exception: it is `app.mcp.server._RefuseNullArguments`, a `tools/call`
interceptor that runs before the SDK ever binds arguments, so it genuinely
needs the protocol.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.search_tasks import SearchAssignee, SearchPreset, search_tasks_body
from app.models import SortOrder, TaskPriority, TaskSort, TaskStatus
from tests.utils.accounts import (
    archive_project,
    create_bot_user,
    create_project,
    create_task_record,
    create_user_headers,
    my_id,
    token_headers,
)
from tests.utils.mcp import ToolError as ProtocolToolError
from tests.utils.mcp import bot_headers, call_tool
from tests.utils.mcp_body import caller_for

API = settings.API_V1_STR
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
IN_THREE_DAYS = TODAY + timedelta(days=3)


def _titles(result: dict[str, object]) -> list[str]:
    tasks = result["tasks"]
    assert isinstance(tasks, list)
    return [task["title"] for task in tasks]


# Filters, combined


def test_narrows_by_title_text_case_insensitively(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    create_task_record(client, owner, "Fix the flaky spec", project_id=project_id)
    create_task_record(client, owner, "Write the newsletter", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, query="FLAKY")
    assert _titles(result) == ["Fix the flaky spec"]


def test_combining_project_and_status_narrows_to_both(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    work = create_project(client, owner, name="Work")
    other = create_project(client, owner, name="Other")
    create_task_record(client, owner, "Todo in Work", project_id=work, status="todo")
    create_task_record(
        client, owner, "In progress in Work", project_id=work, status="in_progress"
    )
    create_task_record(client, owner, "Todo elsewhere", project_id=other, status="todo")
    headers = bot_headers(client, owner, project_ids=[work, other])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, project=work, status=[TaskStatus.TODO])
    assert _titles(result) == ["Todo in Work"]


def test_narrows_by_priority(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Urgent", project_id=project_id, priority="P1")
    create_task_record(client, owner, "Someday", project_id=project_id, priority="P3")
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, priority=TaskPriority.P1)
    assert _titles(result) == ["Urgent"]


def test_narrows_by_due_before_and_due_after(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(
        client, owner, "Due yesterday", project_id=project_id, due_date=str(YESTERDAY)
    )
    create_task_record(
        client, owner, "Due tomorrow", project_id=project_id, due_date=str(TOMORROW)
    )
    create_task_record(
        client,
        owner,
        "Due in three days",
        project_id=project_id,
        due_date=str(IN_THREE_DAYS),
    )
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, due_after="today", due_before="+3d")
    assert sorted(_titles(result)) == ["Due in three days", "Due tomorrow"]


def test_narrows_by_overdue(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(
        client, owner, "Overdue", project_id=project_id, due_date=str(YESTERDAY)
    )
    create_task_record(
        client, owner, "Not due yet", project_id=project_id, due_date=str(TOMORROW)
    )
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, overdue=True)
    assert _titles(result) == ["Overdue"]


def test_narrows_by_parent_task_id(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    create_task_record(client, owner, "Sub", parent_id=root["id"])
    create_task_record(client, owner, "Unrelated", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, parent_task_id=root["id"])
    assert _titles(result) == ["Sub"]


def test_narrows_by_tag(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Tagged", project_id=project_id, tags=["ci"])
    create_task_record(client, owner, "Untagged", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, tag="ci")
    assert _titles(result) == ["Tagged"]


# Names: project and tag, by id and by name, case-insensitively


def test_project_is_accepted_by_name_case_insensitively(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    create_task_record(client, owner, "In Work", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, project="wORK")
    assert _titles(result) == ["In Work"]


def test_ambiguous_project_name_is_refused_with_matching_ids(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    first = create_project(client, owner, name="Launch")
    second = create_project(client, owner, name="Launch")
    headers = bot_headers(client, owner, project_ids=[first, second])
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_tasks_body(db, caller, project="Launch")
    message = str(exc_info.value)
    assert "ambiguous_project_name" in message
    assert first in message
    assert second in message


def test_tag_is_accepted_by_name_case_insensitively_and_by_id(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Tagged", project_id=project_id, tags=["CI"])
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    by_name = search_tasks_body(db, caller, tag="ci")
    assert _titles(by_name) == ["Tagged"]

    r = client.get(f"{API}/tags/", headers=owner)
    assert r.status_code == 200, r.text
    tag_id = next(t["id"] for t in r.json()["data"] if t["name"] == "CI")

    by_id = search_tasks_body(db, caller, tag=tag_id)
    assert _titles(by_id) == ["Tagged"]


def test_unknown_tag_name_narrows_to_nothing_rather_than_refusing(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Untagged", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, tag="no-such-tag")
    assert result["tasks"] == []


# Ids: full id and the short prefix a compact line prints


def test_parent_task_id_accepts_the_short_prefix_a_line_prints(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    create_task_record(client, owner, "Sub", parent_id=root["id"])
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    listed = search_tasks_body(db, caller, query="Root")
    short_id = listed["tasks"][0]["id"]
    assert short_id == root["id"].replace("-", "")[:8]

    result = search_tasks_body(db, caller, parent_task_id=short_id)
    assert _titles(result) == ["Sub"]


def test_ambiguous_short_prefix_is_refused_with_candidates(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    first = create_task_record(client, owner, "First", project_id=project_id)
    second = create_task_record(client, owner, "Second", project_id=project_id)

    # The empty string is a prefix every task's id starts with — a
    # deterministic way to force two candidates, rather than relying on two
    # real ids sharing their first characters by chance.
    with pytest.raises(ToolError) as exc_info:
        search_tasks_body(db, caller, parent_task_id="")
    message = str(exc_info.value)
    assert "ambiguous_id" in message
    # Each full id is paired with its own title in the message, not just
    # present somewhere in it — proof the two candidates are distinguishable
    # from each other, not only from "no match at all".
    assert f"{first['id']} “{first['title']}”" in message
    assert f"{second['id']} “{second['title']}”" in message


# Dates: ISO, today, tomorrow, +<count>d


def test_invalid_date_is_refused(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_tasks_body(db, caller, due_before="next tuesday")
    assert "invalid_date" in str(exc_info.value)


# Nulls


def test_a_null_argument_is_refused_rather_than_treated_as_absent(
    client: TestClient, db: Session
) -> None:
    """
    `app.mcp.server._RefuseNullArguments` inspects the raw JSON arguments of
    a `tools/call`, before the SDK binds anything to `search_tasks`'s own
    parameters — the one check here that genuinely needs the protocol.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])

    try:
        call_tool(client, headers, "search_tasks", {"project": None})
        raise AssertionError("expected a refusal")
    except ProtocolToolError as exc:
        assert "invalid_argument" in exc.message
        assert "project" in exc.message
        assert "null" in exc.message


# Assignee


def test_assignee_self_names_the_connecting_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)
    bot_id = my_id(client, headers)

    create_task_record(client, owner, "Mine", project_id=project_id, assignee_id=bot_id)
    create_task_record(client, owner, "Not mine", project_id=project_id)

    result = search_tasks_body(db, caller, assignee=SearchAssignee.SELF)
    assert _titles(result) == ["Mine"]


def test_assignee_owner_any_bot_and_nobody(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)
    bot_id = my_id(client, headers)
    owner_id = my_id(client, owner)

    create_task_record(
        client, owner, "On owner", project_id=project_id, assignee_id=owner_id
    )
    create_task_record(
        client, owner, "On bot", project_id=project_id, assignee_id=bot_id
    )
    create_task_record(client, owner, "On nobody", project_id=project_id)

    assert _titles(search_tasks_body(db, caller, assignee=SearchAssignee.OWNER)) == [
        "On owner"
    ]
    assert _titles(search_tasks_body(db, caller, assignee=SearchAssignee.ANY_BOT)) == [
        "On bot"
    ]
    assert _titles(search_tasks_body(db, caller, assignee=SearchAssignee.NOBODY)) == [
        "On nobody"
    ]
    assert sorted(
        _titles(search_tasks_body(db, caller, assignee=SearchAssignee.ANY))
    ) == ["On bot", "On nobody", "On owner"]


# open_only and status


def test_open_only_defaults_true_and_excludes_done(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Open", project_id=project_id)
    done = create_task_record(client, owner, "Finished", project_id=project_id)
    r = client.patch(
        f"{API}/tasks/{done['id']}", headers=owner, json={"status": "done"}
    )
    assert r.status_code == 200, r.text
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    assert _titles(search_tasks_body(db, caller)) == ["Open"]


def test_status_done_with_open_only_false_reaches_done_work(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    done = create_task_record(client, owner, "Finished", project_id=project_id)
    r = client.patch(
        f"{API}/tasks/{done['id']}", headers=owner, json={"status": "done"}
    )
    assert r.status_code == 200, r.text
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, status=[TaskStatus.DONE], open_only=False)
    assert _titles(result) == ["Finished"]


def test_status_done_with_open_only_true_matches_nothing(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    done = create_task_record(client, owner, "Finished", project_id=project_id)
    r = client.patch(
        f"{API}/tasks/{done['id']}", headers=owner, json={"status": "done"}
    )
    assert r.status_code == 200, r.text
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, status=[TaskStatus.DONE])
    assert result == {"tasks": [], "count": 0}


# Presets


def test_preset_ready_for_me(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)
    bot_id = my_id(client, headers)

    create_task_record(
        client, owner, "Ready", project_id=project_id, assignee_id=bot_id, status="todo"
    )
    create_task_record(
        client,
        owner,
        "Not ready yet",
        project_id=project_id,
        assignee_id=bot_id,
        status="backlog",
    )
    create_task_record(
        client, owner, "Someone else's todo", project_id=project_id, status="todo"
    )

    result = search_tasks_body(db, caller, preset=SearchPreset.READY_FOR_ME)
    assert _titles(result) == ["Ready"]


def test_preset_my_overdue(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)
    bot_id = my_id(client, headers)

    create_task_record(
        client,
        owner,
        "My overdue",
        project_id=project_id,
        assignee_id=bot_id,
        due_date=str(YESTERDAY),
    )
    create_task_record(
        client,
        owner,
        "Overdue, not mine",
        project_id=project_id,
        due_date=str(YESTERDAY),
    )
    create_task_record(
        client,
        owner,
        "Mine, not overdue",
        project_id=project_id,
        assignee_id=bot_id,
        due_date=str(TOMORROW),
    )

    result = search_tasks_body(db, caller, preset=SearchPreset.MY_OVERDUE)
    assert _titles(result) == ["My overdue"]


def test_preset_recently_filed_sorts_newest_first(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "First", project_id=project_id)
    create_task_record(client, owner, "Second", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, preset=SearchPreset.RECENTLY_FILED)
    assert _titles(result) == ["Second", "First"]


def test_preset_conflicting_with_its_own_filter_is_refused(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_tasks_body(
            db,
            caller,
            preset=SearchPreset.READY_FOR_ME,
            status=[TaskStatus.IN_PROGRESS],
        )
    assert "preset_conflict" in str(exc_info.value)


# Sort and order


def test_sort_by_priority_both_directions(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Low", project_id=project_id, priority="P3")
    create_task_record(client, owner, "High", project_id=project_id, priority="P1")
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    natural = search_tasks_body(db, caller, sort=TaskSort.PRIORITY)
    assert _titles(natural) == ["High", "Low"]

    reversed_ = search_tasks_body(
        db, caller, sort=TaskSort.PRIORITY, order=SortOrder.DESC
    )
    assert _titles(reversed_) == ["Low", "High"]


# Compact lines, the total, and truncation


def test_compact_row_shape_and_subtask_counts(client: TestClient, db: Session) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Work")
    root = create_task_record(
        client,
        owner,
        "Root",
        project_id=project_id,
        priority="P2",
        due_date=str(TOMORROW),
        tags=["ci"],
    )
    sub = create_task_record(client, owner, "Sub", parent_id=root["id"])
    r = client.patch(f"{API}/tasks/{sub['id']}", headers=owner, json={"status": "done"})
    assert r.status_code == 200, r.text
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, query="Root")
    [row] = result["tasks"]
    assert row == {
        "id": root["id"].replace("-", "")[:8],
        "status": "backlog",
        "priority": "P2",
        "due_date": str(TOMORROW),
        "title": "Root",
        "project": "Work",
        "tags": ["ci"],
        "subtasks": {"total": 1, "done": 1},
    }


def test_truncated_result_reports_the_total_and_a_filter_to_narrow_with(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    for i in range(3):
        create_task_record(client, owner, f"Task {i}", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller, limit=2)
    assert result["count"] == 3
    assert len(result["tasks"]) == 2
    assert result["truncated"] is True
    assert result["narrow_with"] == "project"


def test_a_complete_result_is_not_marked_truncated(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    create_task_record(client, owner, "Only one", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    result = search_tasks_body(db, caller)
    assert result["count"] == 1
    assert "truncated" not in result


# Refusals: permission, scope, and the archive


def test_without_read_tasks_permission_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions={}, name="No read"
    )
    headers = token_headers(client, owner, bot["id"])
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_tasks_body(db, caller)
    message = str(exc_info.value)
    assert "permission_not_granted" in message
    assert "read tasks" in message


def test_a_project_outside_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    in_scope = create_project(client, owner, name="In scope")
    outside = create_project(client, owner, name="Outside")
    headers = bot_headers(client, owner, project_ids=[in_scope])
    caller = caller_for(db, headers)

    with pytest.raises(ToolError) as exc_info:
        search_tasks_body(db, caller, project=outside)
    message = str(exc_info.value)
    assert "outside_scope" in message
    assert "Outside" in message


def test_the_archive_is_never_listed_even_though_its_project_is_in_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, name="Shelved")
    create_task_record(client, owner, "Filed before the shelf", project_id=project_id)
    headers = bot_headers(client, owner, project_ids=[project_id])
    caller = caller_for(db, headers)

    # Filed while the project was still live; search_tasks never surfaces it
    # once the project is archived, whatever the bot's scope still says
    # (FR-05.13) — the scope lists the project, not an exemption from the
    # archive.
    r = archive_project(client, owner, project_id)
    assert r.status_code == 200, r.text

    result = search_tasks_body(db, caller)
    assert result == {"tasks": [], "count": 0}
