"""
Which changes put an event in the outbox, and for whom (FR-11.4 to FR-11.7).

Events are read straight from the outbox: what is sent is `test_delivery.py`.
"""

import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import Session

from app import webhook_events
from app.core.config import settings
from app.models import BotUser
from tests.utils.accounts import (
    archive_project,
    create_project,
    create_recurring_task,
    create_task,
    create_task_record,
    create_user_headers,
    create_webhook_bot,
    delete_project,
    delete_task,
    token_headers,
    unarchive_project,
)
from tests.utils.webhooks import outbox, pending

API = settings.API_V1_STR
Headers = dict[str, str]


def _setup(
    client: TestClient, db: Session, **bot_options: Any
) -> tuple[Headers, str, dict[str, Any]]:
    """An owner, a project, and a bot user with both webhooks set."""
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_webhook_bot(client, owner, project_ids=[project_id], **bot_options)
    return owner, project_id, bot


def _update(client: TestClient, headers: Headers, task_id: str, **fields: Any) -> None:
    r = client.patch(f"{API}/tasks/{task_id}", headers=headers, json=fields)
    assert r.status_code == 200, r.text


def _comment(client: TestClient, headers: Headers, task_id: str) -> str:
    r = client.post(
        f"{API}/tasks/{task_id}/comments/", headers=headers, json={"body": "Hello"}
    )
    assert r.status_code == 200, r.text
    comment_id: str = r.json()["id"]
    return comment_id


def _events(db: Session, bot: dict[str, Any]) -> list[tuple[str, str | None]]:
    return [(row.event, str(row.task_id)) for row in pending(db, bot["id"])]


# --- Ready (FR-11.4) ------------------------------------------------------------


def test_a_task_created_in_to_do_for_a_bot_user_is_ready_for_it(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)

    task = create_task_record(
        client,
        owner,
        "Triage",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )

    assert _events(db, bot) == [("task.ready", task["id"])]
    row = pending(db, bot["id"])[0]
    assert row.webhook == "task"
    assert row.task_title == "Triage"
    assert row.comment_id is None


def test_a_task_assigned_while_in_to_do_is_ready_when_assigned(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task(client, owner, project_id=project_id)
    _update(client, owner, task_id, status="todo")
    assert _events(db, bot) == []

    _update(client, owner, task_id, assignee_id=bot["id"])

    assert _events(db, bot) == [("task.ready", task_id)]


def test_a_task_moved_to_to_do_while_assigned_is_ready_when_moved(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client, owner, "T", project_id=project_id, assignee_id=bot["id"]
    )["id"]
    # Assigned a Backlog task: the bot has nothing to do yet.
    assert _events(db, bot) == []

    _update(client, owner, task_id, status="todo")

    assert _events(db, bot) == [("task.ready", task_id)]


def test_a_reopened_task_is_ready_again(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]
    _update(client, owner, task_id, status="done")

    _update(client, owner, task_id, status="todo")

    assert [e for e, _ in _events(db, bot)] == ["task.ready", "task.ready"]


def test_other_statuses_and_other_assignees_are_not_ready(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    other = create_webhook_bot(client, owner, project_ids=[project_id], name="Other")

    for status in ("backlog", "in_progress", "review", "waiting", "done"):
        create_task_record(
            client,
            owner,
            status,
            project_id=project_id,
            status=status,
            assignee_id=bot["id"],
        )
    create_task_record(client, owner, "Mine", project_id=project_id, status="todo")

    assert _events(db, bot) == []
    assert _events(db, other) == []


def test_a_task_leaving_ready_or_changing_while_ready_is_not_an_event(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]
    assert len(pending(db, bot["id"])) == 1

    _update(client, owner, task_id, title="Renamed", priority="P1")
    _update(client, owner, task_id, status="in_progress")
    _update(client, owner, task_id, assignee_id=None)

    assert len(outbox(db, bot["id"])) == 1


def test_reassigning_a_ready_task_to_another_bot_user_readies_it_for_that_one(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    other = create_webhook_bot(client, owner, project_ids=[project_id], name="Other")
    task_id = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]

    _update(client, owner, task_id, assignee_id=other["id"])

    assert _events(db, other) == [("task.ready", task_id)]
    assert len(outbox(db, bot["id"])) == 1


def test_a_bot_user_without_the_task_webhook_is_told_nothing(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db, task=False)

    create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )

    assert outbox(db, bot["id"]) == []


def test_a_subtask_is_ready_like_any_task(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    parent_id = create_task(client, owner, project_id=project_id)

    child = create_task_record(
        client,
        owner,
        "Child",
        parent_id=parent_id,
        status="todo",
        assignee_id=bot["id"],
    )

    assert _events(db, bot) == [("task.ready", child["id"])]


def test_the_next_occurrence_of_a_recurring_task_is_ready_when_it_is_created(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task = create_recurring_task(
        client,
        owner,
        date(2030, 1, 1),
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )
    assert len(pending(db, bot["id"])) == 1

    _update(client, owner, task["id"], status="done")

    events = _events(db, bot)
    assert len(events) == 2
    assert events[1][1] != task["id"]


# --- One event per task for a bulk act -----------------------------------------


def test_a_bulk_act_is_one_event_per_task(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    ids = [create_task(client, owner, project_id=project_id) for _ in range(3)]
    already = create_task_record(
        client,
        owner,
        "Already",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]

    r = client.post(
        f"{API}/tasks/bulk",
        headers=owner,
        json={"task_ids": [*ids, already], "status": "todo", "assignee_id": bot["id"]},
    )
    assert r.status_code == 200, r.text

    events = _events(db, bot)
    # The one that was ready before is not told again.
    assert sorted(task_id for _, task_id in events if task_id != already) == sorted(ids)
    assert [task_id for _, task_id in events].count(already) == 1
    assert len(events) == 4


# --- The bot user's own changes (FR-11.5) -----------------------------------------


def test_a_bots_own_changes_never_call_its_own_webhooks(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    bot_headers = token_headers(client, owner, bot["id"])
    backlog = create_task(client, owner, project_id=project_id)
    _update(client, owner, backlog, assignee_id=bot["id"])

    # It moves its own task to To do, and files one for itself in To do.
    _update(client, bot_headers, backlog, status="todo")
    own = create_task_record(
        client,
        bot_headers,
        "Own",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )
    _comment(client, bot_headers, own["id"])

    assert outbox(db, bot["id"]) == []


def test_another_bot_users_change_calls_the_webhook(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    other = create_webhook_bot(client, owner, project_ids=[project_id], name="Other")
    other_headers = token_headers(client, owner, other["id"])

    task = create_task_record(
        client,
        other_headers,
        "Handed over",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )

    assert _events(db, bot) == [("task.ready", task["id"])]


# --- Restores, unarchives, archived and deleted tasks (FR-11.5, FR-11.7) --------


def _restore(client: TestClient, headers: Headers, action: str, entity_id: str) -> None:
    entries = client.get(
        f"{API}/activity-log/", headers=headers, params={"limit": 200}
    ).json()["data"]
    entry = next(
        e for e in entries if e["action"] == action and e["entity_id"] == entity_id
    )
    r = client.post(f"{API}/activity-log/{entry['id']}/restore", headers=headers)
    assert r.status_code == 200, r.text


def test_restoring_a_task_is_not_an_event(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]
    assert delete_task(client, owner, task_id).status_code == 200

    _restore(client, owner, "task_deleted", task_id)

    assert len(outbox(db, bot["id"])) == 1


def test_restoring_a_project_is_not_an_event(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )
    assert delete_project(client, owner, project_id).status_code == 200

    _restore(client, owner, "project_deleted", project_id)

    assert len(outbox(db, bot["id"])) == 1


def test_unarchiving_a_project_is_not_an_event(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )
    assert archive_project(client, owner, project_id).status_code == 200

    assert unarchive_project(client, owner, project_id).status_code == 200

    assert len(outbox(db, bot["id"])) == 1


def test_a_task_in_an_archived_project_or_a_deleted_task_produces_no_event(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    archived = create_task(client, owner, project_id=project_id)
    archived_child = create_task(client, owner, parent_id=archived)
    gone = create_task(client, owner, project_id=create_project(client, owner, "Q"))
    archive_project(client, owner, project_id)
    delete_task(client, owner, gone)
    db.expire_all()

    # The API refuses to change either, so the rule is checked where the event
    # is decided.
    webhook_events.stage_events(
        db,
        ready=[
            (uuid.UUID(t), uuid.UUID(bot["id"]))
            for t in (archived, archived_child, gone)
        ],
        comment_ids=[],
        actor_bot_user_id=None,
    )
    db.commit()

    assert outbox(db, bot["id"]) == []


def test_a_task_of_another_users_is_never_an_event_for_this_bot_user(
    client: TestClient, db: Session
) -> None:
    _owner, _project_id, bot = _setup(client, db)
    stranger = create_user_headers(client, db)
    task_id = create_task(client, stranger)

    webhook_events.stage_events(
        db,
        ready=[(uuid.UUID(task_id), uuid.UUID(bot["id"]))],
        comment_ids=[],
        actor_bot_user_id=None,
    )
    db.commit()

    assert outbox(db, bot["id"]) == []


def test_a_deleted_bot_user_is_told_nothing(client: TestClient, db: Session) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task(client, owner, project_id=project_id)
    # A bot user that is deleted takes nothing new (FR-08.21), so the rule is
    # checked where the event is decided.
    db.execute(
        update(BotUser)
        .where(BotUser.id == uuid.UUID(bot["id"]))  # type: ignore[arg-type]
        .values(deleted_at=date(2030, 1, 1))
    )
    db.commit()

    webhook_events.stage_events(
        db,
        ready=[(uuid.UUID(task_id), uuid.UUID(bot["id"]))],
        comment_ids=[],
        actor_bot_user_id=None,
    )
    db.commit()

    assert outbox(db, bot["id"]) == []


def test_an_event_that_rolls_back_with_its_change_is_never_sent(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task(client, owner, project_id=project_id)

    webhook_events.stage_events(
        db,
        ready=[(uuid.UUID(task_id), uuid.UUID(bot["id"]))],
        comment_ids=[],
        actor_bot_user_id=None,
    )
    db.flush()
    db.rollback()

    assert outbox(db, bot["id"]) == []


# --- Comments (FR-11.6) ---------------------------------------------------------


def test_a_comment_calls_the_webhook_of_the_assignee(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task(client, owner, project_id=project_id)
    _update(client, owner, task_id, assignee_id=bot["id"])

    comment_id = _comment(client, owner, task_id)

    [row] = pending(db, bot["id"])
    assert (row.event, row.webhook) == ("comment.added", "comment")
    assert str(row.comment_id) == comment_id
    assert str(row.task_id) == task_id


def test_a_comment_calls_the_webhook_of_the_reporter(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    bot_headers = token_headers(client, owner, bot["id"])
    task_id = create_task(client, bot_headers, project_id=project_id)

    _comment(client, owner, task_id)

    assert [e for e, _ in _events(db, bot)] == ["comment.added"]


def test_a_comment_calls_a_bot_user_that_has_commented_on_the_task(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    bot_headers = token_headers(client, owner, bot["id"])
    task_id = create_task(client, owner, project_id=project_id)
    assert _events(db, bot) == []
    _comment(client, owner, task_id)
    # Not involved yet: it is not the assignee or reporter and has not spoken.
    assert _events(db, bot) == []
    _comment(client, bot_headers, task_id)

    _comment(client, owner, task_id)

    assert [e for e, _ in _events(db, bot)] == ["comment.added"]


def test_a_bot_user_not_involved_in_the_task_is_not_called(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task(client, owner, project_id=project_id)

    _comment(client, owner, task_id)

    assert outbox(db, bot["id"]) == []


def test_a_bot_users_own_comment_never_calls_it_but_calls_the_others(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    other = create_webhook_bot(client, owner, project_ids=[project_id], name="Other")
    bot_headers = token_headers(client, owner, bot["id"])
    task_id = create_task_record(
        client, owner, "T", project_id=project_id, assignee_id=bot["id"]
    )["id"]
    _update(client, owner, task_id, assignee_id=other["id"])
    # Both are involved: one by assignment, one by having been assigned and
    # reporting nothing, so make the first one comment to be involved too.
    _comment(client, bot_headers, task_id)
    for event_bot in (bot, other):
        for row in pending(db, event_bot["id"]):
            db.delete(row)
    db.commit()

    _comment(client, bot_headers, task_id)

    assert outbox(db, bot["id"]) == []
    assert [e for e, _ in _events(db, other)] == ["comment.added"]


def test_editing_or_deleting_a_comment_is_not_an_event(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client, owner, "T", project_id=project_id, assignee_id=bot["id"]
    )["id"]
    comment_id = _comment(client, owner, task_id)
    assert len(pending(db, bot["id"])) == 1

    r = client.patch(
        f"{API}/comments/{comment_id}", headers=owner, json={"body": "Edited"}
    )
    assert r.status_code == 200
    assert (
        client.delete(f"{API}/comments/{comment_id}", headers=owner).status_code == 200
    )

    assert len(outbox(db, bot["id"])) == 1


def test_the_comment_webhook_is_separate_from_the_task_webhook(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db, comment=False)
    task_id = create_task_record(
        client, owner, "T", project_id=project_id, assignee_id=bot["id"]
    )["id"]

    _comment(client, owner, task_id)

    assert outbox(db, bot["id"]) == []


def test_a_comment_on_a_task_in_another_users_account_calls_nobody_of_this_owner(
    client: TestClient, db: Session
) -> None:
    _owner, _project_id, bot = _setup(client, db)
    stranger = create_user_headers(client, db)
    task_id = create_task(client, stranger)

    _comment(client, stranger, task_id)

    assert outbox(db, bot["id"]) == []


@pytest.mark.parametrize("kind", ["task", "comment"])
def test_clearing_a_webhook_discards_what_was_waiting_for_it(
    client: TestClient, db: Session, kind: str
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]
    _comment(client, owner, task_id)
    assert len(pending(db, bot["id"])) == 2

    client.delete(f"{API}/bot-users/{bot['id']}/webhooks/{kind}", headers=owner)

    assert [row.webhook for row in pending(db, bot["id"])] == [
        "comment" if kind == "task" else "task"
    ]


def test_deleting_a_bot_user_discards_its_undelivered_events(
    client: TestClient, db: Session
) -> None:
    owner, project_id, bot = _setup(client, db)
    task_id = create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )["id"]
    _comment(client, owner, task_id)
    assert len(pending(db, bot["id"])) == 2

    assert (
        client.delete(f"{API}/bot-users/{bot['id']}", headers=owner).status_code == 200
    )

    assert outbox(db, bot["id"]) == []
    # And what it was assigned stays assigned, so a later change calls nobody.
    _comment(client, owner, task_id)
    assert outbox(db, bot["id"]) == []


def test_no_event_is_written_for_a_project_the_scope_does_not_cover(
    client: TestClient, db: Session
) -> None:
    # A webhook is not narrowed by the scope: the owner assigned the task, and
    # the bot user reads what it can through the REST API (ADR-0009).
    owner, _project_id, bot = _setup(client, db)
    outside = create_project(client, owner, "Outside the scope")

    create_task_record(
        client,
        owner,
        "T",
        project_id=outside,
        status="todo",
        assignee_id=bot["id"],
    )

    assert len(pending(db, bot["id"])) == 1
