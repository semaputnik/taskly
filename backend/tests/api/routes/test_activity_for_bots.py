"""
A bot user reading the activity log, narrowed to its scope (#251, spec #246).

Visibility is the whole of the behaviour here, so these tests are mostly
"this entry is in the feed / this one is not" over fixtures with work both
inside and outside a scope, driven over HTTP with a bot user's token — never
assertions about how the query was built. Prior art: `test_activity_by_actor`
and `test_activity_by_kind` for how a log fixture is built and read,
`test_bot_task_writes` for the scope-and-permission matrix shape.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
    delete_task,
    error_code,
    issue_bot_headers,
    my_id,
    token_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _log(client: TestClient, headers: Headers, **params: Any) -> Any:
    r = client.get(f"{API}/activity-log/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _get(client: TestClient, headers: Headers, **params: Any) -> Any:
    """Like `_log`, but for a call that is expected to fail: the raw response."""
    return client.get(f"{API}/activity-log/", headers=headers, params=params)


def _actions(page: Any) -> list[str]:
    return [entry["action"] for entry in page["data"]]


def _ids(page: Any) -> set[str]:
    return {entry["id"] for entry in page["data"]}


def _comment(client: TestClient, headers: Headers, task_id: str, body: str) -> str:
    r = client.post(
        f"{API}/tasks/{task_id}/comments/", headers=headers, json={"body": body}
    )
    assert r.status_code == 200, r.text
    comment_id: str = r.json()["id"]
    return comment_id


def _bulk(
    client: TestClient, headers: Headers, task_ids: list[str], **body: Any
) -> Any:
    return client.post(
        f"{API}/tasks/bulk", headers=headers, json={"task_ids": task_ids, **body}
    )


def _patch_scope(
    client: TestClient,
    owner: Headers,
    bot_id: str,
    *,
    project_ids: list[str],
    permissions: dict[str, bool],
) -> None:
    r = client.patch(
        f"{API}/bot-users/{bot_id}",
        headers=owner,
        json={"scope": {"project_ids": project_ids, "permissions": permissions}},
    )
    assert r.status_code == 200, r.text


# --- The grant itself -----------------------------------------------------


def test_without_the_grant_the_bot_is_refused_by_name(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client,
        owner,
        project_ids=[project_id],
        permissions={**ALL_PERMISSIONS, "read_activity": False},
    )

    r = _get(client, bot)
    assert r.status_code == 403
    assert error_code(r) == "permission_not_granted"
    assert r.json()["detail"]["permission"] == "read_activity"


def test_with_the_grant_the_bot_reads_its_scope(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    page = _log(client, bot)
    # The project's own creation is in scope, since it is the project itself.
    assert "project_created" in _actions(page)


def test_revoking_the_grant_takes_effect_on_the_next_request(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot_user = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot = token_headers(client, owner, bot_user["id"])
    assert _get(client, bot).status_code == 200

    _patch_scope(
        client,
        owner,
        bot_user["id"],
        project_ids=[project_id],
        permissions={**ALL_PERMISSIONS, "read_activity": False},
    )

    r = _get(client, bot)
    assert r.status_code == 403
    assert error_code(r) == "permission_not_granted"


# --- Scope: in and out ------------------------------------------------------


def test_the_bot_reads_tasks_in_scope_and_nothing_outside_it(
    client: TestClient, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    inside = create_task(client, owner, project_id=in_scope, title="Inside")
    outside = create_task(client, owner, project_id=out_of_scope, title="Outside")
    client.patch(f"{API}/tasks/{inside}", headers=owner, json={"priority": "P1"})
    client.patch(f"{API}/tasks/{outside}", headers=owner, json={"priority": "P1"})

    page = _log(client, bot)

    task_entries = {
        entry["entity_id"] for entry in page["data"] if entry["entity_type"] == "task"
    }
    assert inside in task_entries
    assert outside not in task_entries


def test_the_bot_reads_comments_and_attachments_on_tasks_in_scope(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id)
    _comment(client, owner, task_id, "Noted")

    assert "comment_added" in _actions(_log(client, bot))


def test_the_bot_reads_a_tasks_deletion_and_restore_placed_by_its_project(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id)
    assert delete_task(client, owner, task_id).status_code == 200

    page = _log(client, bot)
    assert "task_deleted" in _actions(page)


def test_nothing_touching_an_archived_project_is_visible_even_when_scoped(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Shelved")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id, title="Shelved task")
    # The scope still lists it: archiving does not touch a bot's scope.
    assert (
        client.post(f"{API}/projects/{project_id}/archive", headers=owner).status_code
        == 200
    )

    page = _log(client, bot)
    assert "project_created" not in _actions(page)
    assert all(entry["entity_id"] != task_id for entry in page["data"])
    # The owner's own feed is unaffected: archiving is not deleting (FR-05.12).
    assert "project_created" in _actions(_log(client, owner))


# --- Batches: all or nothing ------------------------------------------------


def test_a_batch_naming_only_in_scope_tasks_is_visible(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    first = create_task(client, owner, project_id=project_id, title="First")
    second = create_task(client, owner, project_id=project_id, title="Second")
    assert _bulk(client, owner, [first, second], status="done").status_code == 200

    page = _log(client, bot)
    assert "tasks_bulk_changed" in _actions(page)


def test_a_batch_naming_an_out_of_scope_task_is_hidden_whole(
    client: TestClient, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    inside = create_task(client, owner, project_id=in_scope, title="Inside")
    outside = create_task(client, owner, project_id=out_of_scope, title="Outside")
    assert _bulk(client, owner, [inside, outside], status="done").status_code == 200

    bot_page = _log(client, bot)
    # Absent whole, not trimmed to the task in scope: no entry naming the
    # batch's task ids survives, and nothing else stands in for it either —
    # the in-scope task's own `task_created` entry is still there, but no
    # `tasks_bulk_changed` entry is, trimmed or otherwise.
    assert "tasks_bulk_changed" not in _actions(bot_page)
    assert not any(
        inside in entry["details"].get("task_ids", []) for entry in bot_page["data"]
    )
    # The owner still sees the batch whole.
    assert "tasks_bulk_changed" in _actions(_log(client, owner))


# --- A completion that has since been deleted -------------------------------


def test_a_completion_of_a_since_deleted_task_still_reads(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id)
    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"status": "done"})
    assert delete_task(client, owner, task_id).status_code == 200

    page = _log(client, bot, kind="completed")
    assert _actions(page) == ["task_completed"]


# --- Tags: read whatever the scope says -------------------------------------


def test_the_bot_reads_tag_entries_outside_its_scope(
    client: TestClient, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=out_of_scope)
    client.patch(f"{API}/tasks/{task_id}", headers=owner, json={"tags": ["Urgent"]})

    page = _log(client, bot, kind="tags")
    assert _actions(page) == ["tag_created"]


# --- Actors: the owner, the bot itself, a sibling bot -----------------------


def test_the_bot_reads_entries_by_any_actor(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    sibling = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    reader_user = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=ALL_PERMISSIONS,
        name="Reader",
    )
    reader = token_headers(client, owner, reader_user["id"])

    create_task(client, owner, project_id=project_id, title="By the owner")
    create_task(client, sibling, project_id=project_id, title="By the sibling")

    page = _log(client, reader)
    titles = {entry["details"].get("title") for entry in page["data"]}
    assert "By the owner" in titles
    assert "By the sibling" in titles


# --- restorable and the deletion id -----------------------------------------


def test_restorable_and_the_deletion_id_are_null_for_a_bot_set_for_a_human(
    client: TestClient, owner: Headers
) -> None:
    """
    One response model, not a union (#314): a bot user's entry still carries
    both keys — there is nothing to discriminate between shapes any more —
    but `null` for both, meaning withheld, never the `False`/absent a human's
    own entry would never show either. Both sides are asserted here, in one
    test, so the guard cannot drift into checking one shape without the
    other.
    """
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id)
    assert delete_task(client, owner, task_id).status_code == 200

    bot_entry = next(
        e for e in _log(client, bot)["data"] if e["action"] == "task_deleted"
    )
    assert bot_entry["restorable"] is None
    assert bot_entry["deletion_id"] is None

    human_entry = next(
        e for e in _log(client, owner)["data"] if e["action"] == "task_deleted"
    )
    assert human_entry["restorable"] is True
    assert human_entry["deletion_id"] is not None


def test_restore_is_still_refused_to_a_bot(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id)
    assert delete_task(client, owner, task_id).status_code == 200
    entry_id = next(
        e for e in _log(client, owner)["data"] if e["action"] == "task_deleted"
    )["id"]

    r = client.post(f"{API}/activity-log/{entry_id}/restore", headers=bot)
    assert r.status_code == 403
    assert error_code(r) == "human_only"


# --- until, and combining with everything else ------------------------------


def test_until_bounds_the_feed_inclusive_of_its_own_moment(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    create_task(client, owner, project_id=project_id, title="Before")
    moment = _log(client, bot)["data"][0]["created_at"]
    create_task(client, owner, project_id=project_id, title="After")

    page = _log(client, bot, until=moment)
    titles = {entry["details"].get("title") for entry in page["data"]}
    assert "Before" in titles
    assert "After" not in titles


def test_until_combines_with_since_kind_task_project_and_actor(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot_id = my_id(client, bot)
    # The bot does its own work here so the actor narrowing has something of
    # its own to pick out.
    task_id = create_task(client, bot, project_id=project_id, title="Tracked")
    since = _log(client, bot)["data"][0]["created_at"]
    client.patch(f"{API}/tasks/{task_id}", headers=bot, json={"status": "done"})
    until = _log(client, bot)["data"][0]["created_at"]
    create_task(client, owner, project_id=project_id, title="Later, excluded")

    page = _log(
        client,
        bot,
        since=since,
        until=until,
        kind="completed",
        task_id=task_id,
        project_id=project_id,
        actor_bot_user_id=bot_id,
    )
    assert _actions(page) == ["task_completed"]


# --- A task or project the bot cannot reach is a 404, not an empty feed ----


def test_narrowing_by_an_out_of_scope_task_is_not_found(
    client: TestClient, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    outside = create_task(client, owner, project_id=out_of_scope)

    r = _get(client, bot, task_id=outside)
    assert r.status_code == 404


def test_narrowing_by_an_out_of_scope_project_is_not_found(
    client: TestClient, owner: Headers
) -> None:
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )

    r = _get(client, bot, project_id=out_of_scope)
    assert r.status_code == 404


def test_missing_and_out_of_scope_project_give_the_identical_refusal(
    client: TestClient, owner: Headers
) -> None:
    """
    ADR-0011's own point: one answer whatever the reason a bot cannot reach
    the id it named, so a scope refusal can never be told apart from a
    missing one (#322's own acceptance criterion — the project-narrowing
    refusal is decided once, in `app.access.narrowing_project`, so these two
    calls cannot answer differently again).
    """
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )

    outside = _get(client, bot, project_id=out_of_scope)
    missing = _get(client, bot, project_id=str(uuid.uuid4()))

    assert outside.status_code == missing.status_code == 404
    assert outside.json() == missing.json()


def test_missing_and_out_of_scope_task_give_the_identical_refusal(
    client: TestClient, owner: Headers
) -> None:
    """The task-narrowing twin of the project one above: also decided once (`app.access.narrowing_task`)."""
    in_scope = create_project(client, owner, "In scope")
    out_of_scope = create_project(client, owner, "Elsewhere")
    bot = issue_bot_headers(
        client, owner, project_ids=[in_scope], permissions=ALL_PERMISSIONS
    )
    outside_task = create_task(client, owner, project_id=out_of_scope)

    outside = _get(client, bot, task_id=outside_task)
    missing = _get(client, bot, task_id=str(uuid.uuid4()))

    assert outside.status_code == missing.status_code == 404
    assert outside.json() == missing.json()


def test_narrowing_by_an_archived_project_in_scope_is_not_found(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Shelved")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    assert (
        client.post(f"{API}/projects/{project_id}/archive", headers=owner).status_code
        == 200
    )

    r = _get(client, bot, project_id=project_id)
    assert r.status_code == 404


def test_narrowing_by_a_task_in_an_archived_project_in_scope_is_not_found(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner, "Shelved")
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task_id = create_task(client, owner, project_id=project_id)
    assert (
        client.post(f"{API}/projects/{project_id}/archive", headers=owner).status_code
        == 200
    )

    r = _get(client, bot, task_id=task_id)
    assert r.status_code == 404


# --- Regression: a human's feed is untouched --------------------------------


def test_a_humans_feed_is_unaffected_by_the_bot_scope_machinery(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    create_task(client, owner, project_id=project_id)

    page = _log(client, owner)
    for entry in page["data"]:
        assert "restorable" in entry
        assert "deletion_id" in entry
