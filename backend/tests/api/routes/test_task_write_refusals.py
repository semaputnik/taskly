"""
A byte-for-byte record of every refusal the task write paths give today:
creating, updating, completing (through `update_task`'s own `status: done`),
deleting and commenting on a task, including the ones `app.api.access` and
`app.api.deps` raise on those paths — the archive, the scope, a missing
grant, the open-subtasks and delete-cascade confirmations, the due-date
scope, a superseded occurrence, the assignee and recurrence rules.

This is a measurement of the present, not a description of an intention
(#276, part of #275's refusal-vocabulary move). It has to pass before that
move and after it: every case here pins a status, and for a refusal that
carries a code, the code, the message **verbatim**, and every extra key the
body carries today (`project_id`, `permission`, `tags`); a plain-string
refusal is pinned as code-less, exactly as it reads. ADR-0004 already singles
out `task_has_uncompleted_subtasks` and `leave_uncompleted` as wording clients
match on; this file is what makes that guarantee mechanical for every other
refusal these paths give, rather than remembered. A deliberate wording change
is a real product decision, not an accident of refactoring — make it in the
same commit as whatever file changes the words, so this file and the change
tell one story in the diff.

Most refusals are pinned twice: once as the REST API gives them (status,
`detail`), and once as `app.mcp.conventions.refuse`/`refusal` renders them for
an MCP tool call — a `ToolError` whose text is `"<code>: <message>"` — since
an MCP tool calls through to the very same route or access check rather than
re-deriving its own version of the rule. Where a tool wraps a route's refusal
in its own words (`complete_task` naming open subtasks, `delete_task` naming
the ones a cascade would take down) both the REST text (the route's own,
generic) and the MCP text (the tool's, naming names) are pinned, since an MCP
caller never sees the generic one at all: the tool either enriches it or, for
`update_task`'s own `status: done` and `subtasks` arguments, refuses the
request before the route is even called. `_mcp_refused` (below) adds the one
further layer every MCP refusal actually carries: the MCP SDK itself wraps
whatever `ToolError` a tool raised in `Error executing tool <name>: `, so what
an agent receives is never the bare `"<code>: <message>"` on its own.
"""

from datetime import date

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    archive_project,
    create_bot_user,
    create_project,
    create_recurring_task,
    create_task_record,
    create_user_headers,
    issue_bot_headers,
    my_id,
)
from tests.utils.mcp import ToolError, bot_headers, call_tool

API = settings.API_V1_STR

NOT_A_TASK = "00000000-0000-0000-0000-000000000000"
NOT_A_PROJECT = "00000000-0000-0000-0000-000000000000"
NOT_A_COMMENT = "00000000-0000-0000-0000-000000000000"

CREATE_ONLY = {"create_tasks": True}
READ_ONLY_TASKS = {"read_tasks": True}
UPDATE_ONLY = {"update_tasks": True}
DELETE_ONLY = {"delete_tasks": True}
COMMENT_ONLY = {"add_comments": True}


def _patch(
    client: TestClient, headers: dict[str, str], task_id: str, **fields: object
) -> Response:
    return client.patch(f"{API}/tasks/{task_id}", headers=headers, json=fields)


def _add_comment(
    client: TestClient, headers: dict[str, str], task_id: str, body: str
) -> Response:
    return client.post(
        f"{API}/tasks/{task_id}/comments/", headers=headers, json={"body": body}
    )


def _short(full_id: str) -> str:
    """The id a compact MCP line prints (`app.mcp.conventions.short_id`)."""
    return full_id.replace("-", "")[:8]


def _mcp_refused(tool: str, text: str) -> str:
    """
    What `call_tool` raises for a refused call to `tool`: the MCP SDK's own
    wrapper (`mcp.server.mcpserver.tools.base.Tool.run`) around whatever
    `ToolError` the tool itself raised (`app.mcp.conventions.refuse`/
    `refusal`), naming the tool before the refusal text — so the text an
    agent actually sees always starts `Error executing tool <name>: `, not
    just the `"<code>: <message>"` the tool raised.
    """
    return f"Error executing tool {tool}: {text}"


# =============================================================================
# Create
# =============================================================================


def test_creating_outside_a_bots_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    outside = create_project(client, owner, "Outside")
    bot = issue_bot_headers(client, owner, project_ids=[], permissions=CREATE_ONLY)

    r = client.post(
        f"{API}/tasks/", headers=bot, json={"title": "T", "project_id": outside}
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "outside_scope",
        "message": "The project “Outside” is not in this bot user's scope.",
        "project_id": outside,
    }

    mcp = bot_headers(client, owner, project_ids=[], permissions=CREATE_ONLY)
    try:
        call_tool(client, mcp, "create_task", {"title": "T", "project": outside})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "outside_scope: The project “Outside” is not in this bot user's scope.",
        )


def test_creating_in_an_archived_project_is_refused_by_name_for_a_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    shelved = create_project(client, owner, "Shelved")
    assert archive_project(client, owner, shelved).status_code == 200
    bot = issue_bot_headers(
        client, owner, project_ids=[shelved], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/", headers=bot, json={"title": "T", "project_id": shelved}
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "project_archived",
        "message": (
            "The project “Shelved” is archived. Bot users have no access to "
            "archived projects."
        ),
        "project_id": shelved,
    }

    mcp = bot_headers(client, owner, project_ids=[shelved], permissions=CREATE_ONLY)
    try:
        call_tool(client, mcp, "create_task", {"title": "T", "project": shelved})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "project_archived: The project “Shelved” is archived. Bot users "
            "have no access to archived projects.",
        )


def test_creating_without_the_create_grant_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(client, owner, project_ids=[project_id], permissions={})

    r = client.post(
        f"{API}/tasks/", headers=bot, json={"title": "T", "project_id": project_id}
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "permission_not_granted",
        "message": "This bot user is not allowed to create tasks.",
        "permission": "create_tasks",
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions={})
    try:
        call_tool(client, mcp, "create_task", {"title": "T", "project": project_id})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "permission_not_granted: This bot user is not allowed to create tasks.",
        )


def test_a_new_tag_name_without_the_create_tags_grant_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={"title": "T", "project_id": project_id, "tags": ["brand-new"]},
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "permission_not_granted",
        "message": (
            "This bot user is not allowed to create tags, and “brand-new” is "
            "not a tag yet."
        ),
        "permission": "create_tags",
        "tags": ["brand-new"],
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=CREATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "create_task",
            {"title": "T", "project": project_id, "tags": ["brand-new"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "permission_not_granted: This bot user is not allowed to create "
            "tags, and “brand-new” is not a tag yet.",
        )


def test_an_assignee_that_is_someone_elses_id_is_refused_as_a_plain_string(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    stranger = create_user_headers(client, db)
    stranger_id = my_id(client, stranger)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "T",
            "project_id": project_id,
            "assignee_id": stranger_id,
        },
    )
    assert r.status_code == 400, r.text
    assert (
        r.json()["detail"]
        == "A task can only be assigned to you or to one of your bot users"
    )

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=CREATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "create_task",
            {"title": "T", "project": project_id, "assignee": stranger_id},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "invalid_argument: A task can only be assigned to you or to one "
            "of your bot users",
        )


def test_a_recurring_task_cannot_be_created_done(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "T",
            "project_id": project_id,
            "status": "done",
            "recurrence": {"frequency": "weekly"},
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Only an open task can recur"

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=CREATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "create_task",
            {
                "title": "T",
                "project": project_id,
                "status": "done",
                "recurrence": {"frequency": "weekly"},
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task", "invalid_argument: Only an open task can recur"
        )


def test_a_subtask_cannot_be_given_a_recurrence(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "T",
            "parent_id": root["id"],
            "due_date": "2026-03-02",
            "recurrence": {"frequency": "weekly"},
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Only a task at the top of its tree can recur"

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=CREATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "create_task",
            {
                "title": "T",
                "parent_task_id": root["id"],
                "due_date": "2026-03-02",
                "recurrence": {"frequency": "weekly"},
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "invalid_argument: Only a task at the top of its tree can recur",
        )


def test_a_recurring_task_needs_a_due_date_at_creation(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={
            "title": "T",
            "project_id": project_id,
            "recurrence": {"frequency": "weekly"},
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "A recurring task needs a due date"

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=CREATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "create_task",
            {
                "title": "T",
                "project": project_id,
                "recurrence": {"frequency": "weekly"},
            },
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task", "invalid_argument: A recurring task needs a due date"
        )


def test_a_subtask_naming_its_own_project_is_refused_by_the_route(
    client: TestClient, db: Session
) -> None:
    """
    The REST body, alone, reaches `app.api.routes.tasks.create_task`'s own
    check: it has no argument-level equivalent of the MCP tool's earlier one
    below, so this exact plain string is a REST-only refusal.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=CREATE_ONLY
    )

    r = client.post(
        f"{API}/tasks/",
        headers=bot,
        json={"title": "T", "parent_id": root["id"], "project_id": project_id},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "A subtask belongs to the project of its parent"


def test_a_subtask_naming_its_own_project_is_refused_earlier_by_the_mcp_tool(
    client: TestClient, db: Session
) -> None:
    """
    `create_task` (the MCP tool) refuses this combination itself, in its own
    words, before `app.api.routes.tasks.create_task` is ever called — so an
    MCP caller never sees the route's own message (pinned above) for this
    case at all.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=CREATE_ONLY)

    try:
        call_tool(
            client,
            mcp,
            "create_task",
            {"title": "T", "parent_task_id": root["id"], "project": project_id},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task",
            "invalid_argument: A subtask belongs to the project of its "
            "parent; name no project for it.",
        )


def test_creating_against_an_unknown_project_is_a_code_less_404(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot = issue_bot_headers(client, owner, project_ids=[], permissions=CREATE_ONLY)

    r = client.post(
        f"{API}/tasks/", headers=bot, json={"title": "T", "project_id": NOT_A_PROJECT}
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Project not found"

    mcp = bot_headers(client, owner, project_ids=[], permissions=CREATE_ONLY)
    try:
        call_tool(client, mcp, "create_task", {"title": "T", "project": NOT_A_PROJECT})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "create_task", "not_found: Project not found"
        )


# =============================================================================
# Update
# =============================================================================


def test_updating_without_the_update_grant_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(client, owner, project_ids=[project_id], permissions={})

    r = _patch(client, bot, task["id"], title="Changed")
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "permission_not_granted",
        "message": "This bot user is not allowed to update tasks.",
        "permission": "update_tasks",
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions={})
    try:
        call_tool(client, mcp, "update_task", {"task_id": task["id"], "title": "X"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "permission_not_granted: This bot user is not allowed to update tasks.",
        )


def test_moving_a_task_out_of_a_bots_scope_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    source = create_project(client, owner, "Source")
    outside = create_project(client, owner, "Outside")
    task = create_task_record(client, owner, "T", project_id=source)
    bot = issue_bot_headers(
        client, owner, project_ids=[source], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], project_id=outside)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "outside_scope",
        "message": "The project “Outside” is not in this bot user's scope.",
        "project_id": outside,
    }

    mcp = bot_headers(client, owner, project_ids=[source], permissions=UPDATE_ONLY)
    try:
        call_tool(
            client, mcp, "update_task", {"task_id": task["id"], "project": outside}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "outside_scope: The project “Outside” is not in this bot user's scope.",
        )


def test_updating_a_task_in_an_archived_project_is_refused_by_name_for_the_owner(
    client: TestClient, db: Session
) -> None:
    """
    The human shape of the archive refusal (409, `archived_refusal`): a bot
    never reaches it on this path at all, since `_refuse_bot_project` already
    refuses it with the 403 shape pinned above before `require_project_writable`
    runs — an MCP caller is always a bot (ADR-0012), so there is no MCP
    rendering of this 409 shape to pin.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    assert archive_project(client, owner, project_id).status_code == 200

    r = _patch(client, owner, task["id"], title="Changed")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == {
        "code": "project_archived",
        "message": (
            "The project “Shelved” is archived, so it and its tasks are "
            "read-only. Unarchive it to make changes."
        ),
        "project_id": project_id,
    }


def test_a_task_must_belong_to_a_project(client: TestClient, db: Session) -> None:
    """
    REST-only: nothing in `update_task` (the MCP tool)'s `project` argument
    can send an explicit `null` — there is no `clear` entry for `project`
    either (its own docstring: "a task always has... a project") — so this
    `model_fields_set` path is only reachable by a client sending the field
    itself, the way the REST body below does.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = client.patch(
        f"{API}/tasks/{task['id']}", headers=bot, json={"project_id": None}
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "A task must belong to a project"


def test_a_subtask_cannot_be_moved_between_projects(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    other = create_project(client, owner, "Other")
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id, other], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, child["id"], project_id=other)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "A subtask follows its parent's project; move the task at the top "
        "of the tree instead"
    )

    mcp = bot_headers(
        client, owner, project_ids=[project_id, other], permissions=UPDATE_ONLY
    )
    try:
        call_tool(
            client, mcp, "update_task", {"task_id": child["id"], "project": other}
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "invalid_argument: A subtask follows its parent's project; move "
            "the task at the top of the tree instead",
        )


def test_the_subtasks_directive_only_applies_to_closing(
    client: TestClient, db: Session
) -> None:
    """
    REST-only: `update_task` (the MCP tool) takes no `subtasks` argument at
    all — only `complete_task` does, and it always sends `status: done`
    alongside it — so this mismatch (`subtasks` sent without `status: done`)
    cannot be constructed through any MCP tool.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], subtasks="complete")
    assert r.status_code == 400, r.text
    assert (
        r.json()["detail"]
        == "`subtasks` only applies to a request that moves the task to done"
    )


def test_closing_a_parent_with_open_subtasks_is_refused_generically_over_rest(
    client: TestClient, db: Session
) -> None:
    """
    The route's own refusal (`task_has_uncompleted_subtasks`, ADR-0004) only
    says there is something in the way. An MCP caller never sees this exact
    generic message: `update_task` (the tool) refuses `status: done` outright
    before the route runs at all (pinned below), and `complete_task` is what
    reaches this refusal, enriching it with the subtasks themselves (also
    pinned below) — so this generic text is REST-only.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    create_task_record(client, owner, "Child", parent_id=root["id"])
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, root["id"], status="done")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == {
        "code": "task_has_uncompleted_subtasks",
        "message": (
            "This task has open subtasks. Say whether they stay as they are "
            "or are done too."
        ),
    }


def test_update_task_refuses_status_done_before_the_route_even_runs(
    client: TestClient, db: Session
) -> None:
    """
    `update_task` (the MCP tool)'s own boundary with `complete_task`: moving a
    task to `done` through this tool is refused in the tool's own words,
    pointing at `complete_task`, before `app.api.routes.tasks.update_task` is
    ever called — so the route's various `status: done` refusals (open
    subtasks, the next occurrence) never reach an MCP caller through this
    tool at all.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)

    try:
        call_tool(client, mcp, "update_task", {"task_id": task["id"], "status": "done"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "invalid_argument: update_task does not move a task to done. Use "
            "complete_task to close it — that is where the question about "
            "open subtasks belongs.",
        )


def test_a_deleted_bot_user_takes_no_new_assignment(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    retired = create_bot_user(
        client, owner, project_ids=[], permissions=READ_ONLY_TASKS, name="Retired"
    )
    assert (
        client.delete(f"{API}/bot-users/{retired['id']}", headers=owner).status_code
        == 200
    )
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], assignee_id=retired["id"])
    assert r.status_code == 400, r.text
    assert (
        r.json()["detail"] == "The bot user “Retired” is deleted and takes no new tasks"
    )

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "update_task",
            {"task_id": task["id"], "assignee": retired["id"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "invalid_argument: The bot user “Retired” is deleted and takes no new tasks",
        )


def test_a_recurring_task_needs_a_due_date_when_one_is_cleared(
    client: TestClient, db: Session
) -> None:
    """
    The same literal text as creation's recurrence-needs-a-due-date refusal
    (pinned above): `_check_recurrence_update`'s own `elif` branch reaches it
    a second way, by clearing `due_date` off a task whose recurrence is left
    as it is.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = client.patch(f"{API}/tasks/{task['id']}", headers=bot, json={"due_date": None})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "A recurring task needs a due date"

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "update_task",
            {"task_id": task["id"], "clear": ["due_date"]},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task", "invalid_argument: A recurring task needs a due date"
        )


def test_moving_an_open_occurrences_due_date_needs_a_scope(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], due_date="2026-03-04")
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == {
        "code": "due_date_scope_required",
        "message": (
            "This task recurs. Say whether the new due date applies to this "
            "occurrence only or to this and all following ones."
        ),
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "update_task",
            {"task_id": task["id"], "due_date": "2026-03-04"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "due_date_scope_required: This task recurs. Say whether the new "
            "due date applies to this occurrence only or to this and all "
            "following ones.",
        )


def test_a_due_date_scope_is_refused_where_there_is_no_series_to_reschedule(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], due_date_scope="this_occurrence")
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "`due_date_scope` only applies to changing the due date of a "
        "recurring task that is open"
    )

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "update_task",
            {"task_id": task["id"], "due_date_scope": "this_occurrence"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "invalid_argument: `due_date_scope` only applies to changing the "
            "due date of a recurring task that is open",
        )


def test_a_superseded_occurrence_cannot_be_reopened(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    assert _patch(client, owner, task["id"], status="done").status_code == 200
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], status="todo")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == {
        "code": "occurrence_superseded",
        "message": (
            "A later occurrence of this recurring task already exists. Only "
            "the latest occurrence can be reopened."
        ),
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    try:
        call_tool(client, mcp, "update_task", {"task_id": task["id"], "status": "todo"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "occurrence_superseded: A later occurrence of this recurring "
            "task already exists. Only the latest occurrence can be reopened.",
        )


def test_changing_a_recurrence_is_refused_once_the_task_is_done(
    client: TestClient, db: Session
) -> None:
    """
    `update_task` (the MCP tool) gained a `recurrence` argument (#304), so
    this refusal — unlike before — is reachable through MCP too, the same
    way every other recurrence rule in this file already was.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_recurring_task(client, owner, date(2026, 3, 2), project_id=project_id)
    assert _patch(client, owner, task["id"], status="done").status_code == 200
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=UPDATE_ONLY
    )

    r = _patch(client, bot, task["id"], recurrence={"frequency": "daily"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Only an open task can change how it recurs"

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    try:
        call_tool(
            client,
            mcp,
            "update_task",
            {"task_id": task["id"], "recurrence": {"frequency": "daily"}},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "update_task",
            "invalid_argument: Only an open task can change how it recurs",
        )


def test_updating_an_unknown_task_is_a_code_less_404(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot = issue_bot_headers(client, owner, project_ids=[], permissions=UPDATE_ONLY)

    r = _patch(client, bot, NOT_A_TASK, title="X")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Task not found"

    mcp = bot_headers(client, owner, project_ids=[], permissions=UPDATE_ONLY)
    try:
        call_tool(client, mcp, "update_task", {"task_id": NOT_A_TASK, "title": "X"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused("update_task", "not_found: Task not found")


# =============================================================================
# Completing (closing: `status: done`)
# =============================================================================


def test_closing_a_parent_with_open_subtasks_is_refused_naming_them_over_mcp(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)

    try:
        call_tool(client, mcp, "complete_task", {"task_id": root["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "complete_task",
            f"task_has_uncompleted_subtasks: “Root” has 1 open subtask: "
            f'{_short(child["id"])} “Child”. Send `subtasks: "complete"` to '
            f'close them too, or `subtasks: "leave_uncompleted"` to leave '
            f"each where it is.",
        )


def test_the_subtasks_directive_sent_on_a_call_that_closes_nothing_is_refused(
    client: TestClient, db: Session
) -> None:
    """
    `complete_task`'s own case, with no REST equivalent: the single-task
    REST route has no notion of "a request that closes nothing" — it just
    writes `status: done` again, a no-op, if there are no open subtasks to
    object to. Only `complete_task` (the MCP tool) distinguishes an
    already-done task and refuses `subtasks` sent alongside it.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)
    call_tool(client, mcp, "complete_task", {"task_id": task["id"]})

    try:
        call_tool(
            client,
            mcp,
            "complete_task",
            {"task_id": task["id"], "subtasks": "complete"},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "complete_task",
            "invalid_argument: “T” is already done. `subtasks` only applies "
            "to a call that closes something.",
        )


def test_a_comment_offered_with_a_close_is_refused_by_its_own_grant_first(
    client: TestClient, db: Session
) -> None:
    """
    `complete_task`'s own grant check, ahead of anything closing: the same
    `permission_not_granted`/`add_comments` shape pinned under "Commenting"
    below, reached a second way.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=UPDATE_ONLY)

    try:
        call_tool(
            client,
            mcp,
            "complete_task",
            {"task_id": task["id"], "comment": "Done."},
        )
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "complete_task",
            "permission_not_granted: This bot user is not allowed to add comments.",
        )


# =============================================================================
# Delete
# =============================================================================


def test_deleting_without_the_delete_grant_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(client, owner, project_ids=[project_id], permissions={})

    r = client.delete(f"{API}/tasks/{task['id']}", headers=bot)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "permission_not_granted",
        "message": "This bot user is not allowed to delete tasks.",
        "permission": "delete_tasks",
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions={})
    try:
        call_tool(client, mcp, "delete_task", {"task_id": task["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "delete_task",
            "permission_not_granted: This bot user is not allowed to delete tasks.",
        )


def test_deleting_a_task_with_subtasks_is_refused_generically_over_rest(
    client: TestClient, db: Session
) -> None:
    """
    The route's own refusal (`task_has_subtasks`, FR-01.12) only says
    subtasks are in the way; `delete_task` (the MCP tool) is what enriches it
    with the subtree itself (pinned below), so this exact text is REST-only.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    create_task_record(client, owner, "Child", parent_id=root["id"])
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=DELETE_ONLY
    )

    r = client.delete(f"{API}/tasks/{root['id']}", headers=bot)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == {
        "code": "task_has_subtasks",
        "message": (
            "This task has subtasks, which would be deleted with it. "
            "Confirm with delete_subtasks to go ahead."
        ),
    }


def test_deleting_a_task_with_subtasks_names_them_over_mcp(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    root = create_task_record(client, owner, "Root", project_id=project_id)
    child = create_task_record(client, owner, "Child", parent_id=root["id"])
    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=DELETE_ONLY)

    try:
        call_tool(client, mcp, "delete_task", {"task_id": root["id"]})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "delete_task",
            f"task_has_subtasks: “Root” has 1 subtask, which would be "
            f"deleted with it: {_short(child['id'])} “Child”. Send "
            f"`delete_subtasks: true` to confirm.",
        )


def test_deleting_an_unknown_task_is_a_code_less_404(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot = issue_bot_headers(client, owner, project_ids=[], permissions=DELETE_ONLY)

    r = client.delete(f"{API}/tasks/{NOT_A_TASK}", headers=bot)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Task not found"

    mcp = bot_headers(client, owner, project_ids=[], permissions=DELETE_ONLY)
    try:
        call_tool(client, mcp, "delete_task", {"task_id": NOT_A_TASK})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused("delete_task", "not_found: Task not found")


# =============================================================================
# Commenting
# =============================================================================


def test_commenting_without_the_add_comments_grant_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(client, owner, project_ids=[project_id], permissions={})

    r = _add_comment(client, bot, task["id"], "Note")
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "permission_not_granted",
        "message": "This bot user is not allowed to add comments.",
        "permission": "add_comments",
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions={})
    try:
        call_tool(client, mcp, "comment_task", {"task_id": task["id"], "body": "Note"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "comment_task",
            "permission_not_granted: This bot user is not allowed to add comments.",
        )


def test_reading_comments_without_the_read_grant_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    """
    REST-only: reading a task's comments shares `app.api.access.get_task`'s
    `read_tasks` permission with every other read, but no MCP tool among the
    task write paths this file covers reads comments on its own — `get_task`
    (the read-only tool) is out of this ticket's scope, and `complete_task`'s
    optional comment is checked against `add_comments`, pinned above, never
    against `read_tasks`.
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(client, owner, project_ids=[project_id], permissions={})

    r = client.get(f"{API}/tasks/{task['id']}/comments/", headers=bot)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "permission_not_granted",
        "message": "This bot user is not allowed to read tasks.",
        "permission": "read_tasks",
    }


def test_editing_a_bot_users_comment_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    """
    REST-only: `update_comment`/`delete_comment` take only `CurrentUser`
    (never a `Caller`), so no bot token — and no MCP tool, which is always a
    bot — reaches either route at all (FR-03.2, FR-08.10).
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )
    comment = _add_comment(client, bot, task["id"], "By the bot").json()

    r = client.patch(
        f"{API}/comments/{comment['id']}", headers=owner, json={"body": "Hijacked"}
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "comment_by_bot",
        "message": (
            "This comment was written by a bot user. Comments from bot "
            "users cannot be edited or deleted."
        ),
    }


def test_a_bot_cannot_edit_or_delete_any_comment_at_all(
    client: TestClient, db: Session
) -> None:
    """
    REST-only, the mirror of the case above: a bot token hitting
    `update_comment`/`delete_comment` never gets as far as `comment_by_bot` —
    `get_current_user` (`app.api.deps`) refuses it outright, for what it is
    rather than for a permission it lacks (FR-08.2).
    """
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    task = create_task_record(client, owner, "T", project_id=project_id)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )
    comment = _add_comment(client, owner, task["id"], "By the owner").json()

    r = client.patch(
        f"{API}/comments/{comment['id']}", headers=bot, json={"body": "Rewritten"}
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "human_only",
        "message": "Bot users cannot use this endpoint.",
    }


def test_commenting_on_an_archived_project_is_refused_by_name_for_a_bot(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner, "Shelved")
    task = create_task_record(client, owner, "T", project_id=project_id)
    assert archive_project(client, owner, project_id).status_code == 200
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=COMMENT_ONLY
    )

    r = _add_comment(client, bot, task["id"], "Note")
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {
        "code": "project_archived",
        "message": (
            "The project “Shelved” is archived. Bot users have no access to "
            "archived projects."
        ),
        "project_id": project_id,
    }

    mcp = bot_headers(client, owner, project_ids=[project_id], permissions=COMMENT_ONLY)
    try:
        call_tool(client, mcp, "comment_task", {"task_id": task["id"], "body": "Note"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused(
            "comment_task",
            "project_archived: The project “Shelved” is archived. Bot users "
            "have no access to archived projects.",
        )


def test_commenting_on_an_unknown_task_is_a_code_less_404(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot = issue_bot_headers(client, owner, project_ids=[], permissions=COMMENT_ONLY)

    r = _add_comment(client, bot, NOT_A_TASK, "Note")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Task not found"

    mcp = bot_headers(client, owner, project_ids=[], permissions=COMMENT_ONLY)
    try:
        call_tool(client, mcp, "comment_task", {"task_id": NOT_A_TASK, "body": "Note"})
        raise AssertionError("expected a refusal")
    except ToolError as exc:
        assert exc.message == _mcp_refused("comment_task", "not_found: Task not found")


def test_editing_an_unknown_comment_is_a_code_less_404(
    client: TestClient, db: Session
) -> None:
    """REST-only: see the two comment-editing cases above."""
    owner = create_user_headers(client, db)

    r = client.patch(
        f"{API}/comments/{NOT_A_COMMENT}", headers=owner, json={"body": "X"}
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Comment not found"
