"""
`app.unit_of_work.UnitOfWork` itself (#284, ADR-0013): the collapse risk the
ADR names, made to happen on purpose, and the delivery loop woken once for
an act that stages more than one outbox row — contrasted against the two
commits `app.tasks.complete` and `app.comments.comment` used to make on the
one `Session` an MCP call or a request opens, before this ticket gave each
operation a transaction of its own.

The acceptance test for a failure anywhere inside an act leaving nothing
behind — closing a task with a comment the caller may not leave, and
asserting the task is still open — already exists and needed no change:
`tests/mcp/test_complete_task.py::
test_a_comment_without_the_grant_is_refused_by_name_before_anything_closes`
pins it, true already from `app.tasks.complete`'s own check ordering (the
comment grant is checked before anything closes) and true now for the
reason beyond ordering too: an act that got further before failing would
roll back exactly as completely. Likewise the attachment exception's own
test, `tests/api/routes/test_attachments.py::
test_downloading_an_attachment_whose_bytes_are_missing_is_a_404`, needed no
change — `app.repositories.comments.create_attachment` is not a path any of
#284's five operations drive.
"""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import activity, crud, webhooks
from app.core.db import engine
from app.models import (
    ActivityEntry,
    BotPermissions,
    BotScope,
    BotUserCreate,
    TaskCreate,
    TaskPriority,
    User,
    UserCreate,
)
from app.unit_of_work import UnitOfWork
from tests.utils.accounts import (
    create_bot_user,
    create_project,
    create_recurring_task,
    create_user_headers,
    my_id,
    set_webhook,
    token_headers,
)
from tests.utils.mcp import call_tool
from tests.utils.utils import random_email


def _entries(session: Session, owner_id: uuid.UUID) -> list[ActivityEntry]:
    """Every entry an owner's account carries, oldest first."""
    session.expire_all()
    return list(
        session.exec(
            select(ActivityEntry)
            .where(ActivityEntry.owner_id == owner_id)
            .order_by(col(ActivityEntry.position))
        ).all()
    )


def test_one_unit_of_work_touching_one_entity_twice_is_one_entry_not_two() -> None:
    """
    `tests/api/routes/test_composite_act_entries.py::
    test_two_commits_touching_one_entity_are_two_entries_not_one` (#278) pins
    two *separate* transactions touching one task as two entries, each with
    its own partial `changes` — the shape nothing in the product makes today,
    built by hand to give the collapse risk something to fail against. This
    is the risk itself, made real: the same two edits, folded into *one*
    `UnitOfWork`, are diffed by `app.activity._write` exactly once, start to
    finish, and land as a single entry describing the net change rather than
    two recording that it was two decisions.

    No operation #284 moved onto `UnitOfWork` touches one entity twice within
    its own act (ADR-0013's own accounting), so there is no real path to
    reuse for this — built directly against `UnitOfWork`, the shape a future
    act that did touch one entity twice would take, and the canary for it:
    if a later `UnitOfWork` silently committed more than once per act, this
    would start seeing two entries instead of one and fail.
    """
    with Session(engine) as session:
        owner = crud.create_user(
            session=session, user_create=UserCreate(email=random_email())
        )
        inbox = crud.get_inbox_project(session=session, owner_id=owner.id)
        bot = crud.create_bot_user(
            session=session,
            bot_user_create=BotUserCreate(
                name="Editor",
                scope=BotScope(project_ids=[], permissions=BotPermissions()),
            ),
            owner_id=owner.id,
        )
        activity.set_bot_actor(session, bot.id)
        task = crud.create_task(
            session=session,
            task_create=TaskCreate(title="Draft the report"),
            project_id=inbox.id,
            owner_id=owner.id,
            reporter=crud.Reporter(bot_user_id=bot.id),
        )
        seen = _entries(session, owner.id)

        # Both edits inside one `UnitOfWork`, where #278's own test used two
        # separate commits for the contrast.
        with UnitOfWork(session):
            task.title = "Draft the quarterly report"
            session.add(task)
            task.priority = TaskPriority.P1
            session.add(task)

        entries = _entries(session, owner.id)[len(seen) :]
        [merged] = entries
        assert merged.action == "task_changed"
        assert merged.entity_id == task.id
        # One entry, carrying both changes — never the two #278 pins for the
        # same edits across two transactions.
        assert merged.details["changes"] == {
            "title": {
                "from": "Draft the report",
                "to": "Draft the quarterly report",
            },
            "priority": {"from": None, "to": "P1"},
        }
        assert merged.actor_bot_user_id == bot.id
        assert merged.actor_id is None

        # Cleanup for the same reason #278's own direct-`Session` test gives:
        # this account is never through the suite's shared `db` fixture, so
        # nothing else empties it at the end of the run.
        session.delete(owner)
        session.commit()


def test_an_act_that_stages_two_deliveries_wakes_the_loop_once(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Before #284, `app.mcp.tools.complete_task` reached the database as the
    two commits #278 names: closing the task (plus the next occurrence the
    recurrence spawns) in one, the comment in a second. Each commit that
    stages an outbox row wakes the delivery loop
    (`app.webhook_events._wake`, FR-11.10) — so an act whose two commits
    *both* stage one, under that shape, would have woken the loop twice for
    what the caller experiences as a single call.

    The Doer bot stays the assignee across the close (the request never
    touches `assignee_id`), so the next occurrence it spawns is a `task.
    ready` delivery of its own (FR-11.4), distinct from the `comment_added`
    delivery the note adds a moment later (FR-11.6) — two deliveries, staged
    by what `app.tasks.complete`'s own `UnitOfWork` (#284) now makes one
    transaction, and so one wake-up.
    """
    calls: list[None] = []
    monkeypatch.setattr(webhooks, "wake", lambda: calls.append(None))

    owner = create_user_headers(client, db)
    owner_id = uuid.UUID(my_id(client, owner))
    project_id = create_project(client, owner, "Garden")

    doer = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions={"create_tasks": True},
        name="Doer",
    )
    set_webhook(client, owner, doer["id"], "task", "https://hooks.example.com/doer")
    set_webhook(client, owner, doer["id"], "comment", "https://hooks.example.com/doer")

    closer = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions={"update_tasks": True, "add_comments": True},
        name="Closer",
    )
    closer_headers = token_headers(client, owner, closer["id"])

    task = create_recurring_task(
        client,
        owner,
        date(2026, 3, 2),
        project_id=project_id,
        assignee_id=doer["id"],
    )

    result = call_tool(
        client,
        closer_headers,
        "complete_task",
        {"task_id": task["id"], "comment": "Done for this week."},
    )
    assert result["status"] == "done"
    assert result["next_occurrence"]["due_date"] == "2026-03-09"

    # One wake-up, not the two the act's two outbox rows would have earned
    # it under two commits — FR-11.10's "at once" still holds either way.
    assert len(calls) == 1

    owner_row = db.get(User, owner_id)
    assert owner_row is not None
    db.delete(owner_row)
    db.commit()
