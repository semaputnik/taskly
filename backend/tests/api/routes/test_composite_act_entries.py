"""
Pin the activity entries and webhook outbox rows a composite act produces
today, before #284 gives the operation a unit of work.

`app.activity._collect` (a `before_flush` listener) snapshots an entity's
state the moment a change to it is first seen; `app.activity._write` (a
`before_commit` listener) diffs that snapshot against the entity's state
right before commit, **once per transaction**. Two commits that each touch
the *same* entity therefore write two entries today, one per commit, each
with its own partial `changes` — while the identical two edits folded into
one transaction would be diffed exactly once, start to finish, and write a
single entry describing the net change. No request or MCP call today commits
twice against one entity within what the caller experiences as one act, so
nothing in the suite would notice a unit-of-work refactor that merged two
such writes and quietly lost an entry. This file is what notices: it fails
the moment either test below stops matching, which is also what happens if
the entry list is changed on purpose — in which case the fix is to edit the
test in the same commit as whatever changed the behaviour, not to treat a
new failure here as this file being stale.

`test_closing_a_recurring_task_with_a_note_is_three_entries_and_one_delivery`
pins the first case named by #278: the act `app.mcp.tools.complete_task`
already performs across two commits on one `Session` — closing a recurring
task (which moves it to done and spawns its next occurrence, in
`app.api.routes.tasks.update_task`'s own commit) and leaving a note on it (in
`app.api.routes.comments.create_comment`'s own commit, called straight after
on the same session). `test_two_commits_touching_one_entity_are_two_entries_not_one`
pins the second: an act that touches *one* entity twice across two commits,
which nothing in the product does today, built directly against a `Session`
to give the collapse risk above something concrete to fail against.
"""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import activity, crud
from app.core.config import settings
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
    WebhookEventType,
    WebhookKind,
)
from tests.utils.accounts import (
    create_bot_user,
    create_project,
    create_user_headers,
    my_id,
    set_webhook,
    token_headers,
)
from tests.utils.mcp import call_tool
from tests.utils.utils import random_email
from tests.utils.webhooks import outbox

API = settings.API_V1_STR

# `complete_task` needs both: the grant to move the task to done, and the
# grant to leave the note in the same call (checked ahead of the close, per
# `app.mcp.tools.complete_task`'s own docstring).
CLOSER_PERMISSIONS = {"update_tasks": True, "add_comments": True}
# Enough to file the task the Closer bot will later close.
WATCHER_PERMISSIONS = {"create_tasks": True}


def _entries(db: Session, owner_id: uuid.UUID) -> list[ActivityEntry]:
    """Every entry an owner's account carries, oldest first."""
    db.expire_all()
    return list(
        db.exec(
            select(ActivityEntry)
            .where(ActivityEntry.owner_id == owner_id)
            .order_by(col(ActivityEntry.position))
        ).all()
    )


def _full_task_id(client: TestClient, headers: dict[str, str], short: str) -> str:
    """The full id a short prefix (`next_occurrence["id"]`) names."""
    r = client.get(f"{API}/tasks/", headers=headers)
    assert r.status_code == 200, r.text
    [found] = [
        t for t in r.json()["data"] if t["id"].replace("-", "").startswith(short)
    ]
    full_id: str = found["id"]
    return full_id


def test_closing_a_recurring_task_with_a_note_is_three_entries_and_one_delivery(
    client: TestClient, db: Session
) -> None:
    """
    The composite act #278 names: a bot closes its own recurring task and
    leaves a note, in one MCP call that reaches the database as the two
    commits `complete_task` always has — closing (plus the next occurrence
    the recurrence creates) first, the comment second.

    Entries, by action and in order: the completion, the next occurrence's
    creation, and the comment — each attributed to the Closer bot, never to
    the owner (FR-10.2). Outbox rows: the Closer bot is both the actor and
    the next occurrence's own assignee, so the ready pair `stage_events`
    would otherwise stage for it is the one FR-11.5 drops — a bot is never
    told of its own work — leaving its outbox empty; the Watcher bot, which
    filed the task and so counts as involved (FR-11.6) without being the
    comment's author, is the one delivery this act stages.
    """
    owner = create_user_headers(client, db)
    owner_id = uuid.UUID(my_id(client, owner))
    project_id = create_project(client, owner, "Garden")

    closer = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=CLOSER_PERMISSIONS,
        name="Closer",
    )
    watcher = create_bot_user(
        client,
        owner,
        project_ids=[project_id],
        permissions=WATCHER_PERMISSIONS,
        name="Watcher",
    )
    # Both webhooks set for the Closer bot, so its empty outbox below is the
    # self-exclusion this test pins and not just an unset URL; only the
    # comment webhook is needed to show the Watcher bot is told.
    set_webhook(client, owner, closer["id"], "task", "https://hooks.example.com/closer")
    set_webhook(
        client, owner, closer["id"], "comment", "https://hooks.example.com/closer"
    )
    set_webhook(
        client, owner, watcher["id"], "comment", "https://hooks.example.com/watcher"
    )
    closer_headers = token_headers(client, owner, closer["id"])
    watcher_headers = token_headers(client, owner, watcher["id"])

    due = date(2026, 3, 2)
    r = client.post(
        f"{API}/tasks/",
        headers=watcher_headers,
        json={
            "title": "Water the plants",
            "project_id": project_id,
            "due_date": due.isoformat(),
            "recurrence": {"frequency": "weekly"},
            # Assigned to itself: the Closer bot is about to close its own
            # recurring work, the shape AC3 names.
            "assignee_id": closer["id"],
        },
    )
    assert r.status_code == 200, r.text
    task = r.json()

    seen = _entries(db, owner_id)

    result = call_tool(
        client,
        closer_headers,
        "complete_task",
        {"task_id": task["id"], "comment": "Watered and fed."},
    )
    assert result["status"] == "done"
    next_occurrence = result["next_occurrence"]
    next_due = (due + timedelta(days=7)).isoformat()
    assert next_occurrence["due_date"] == next_due
    successor_id = _full_task_id(client, owner, next_occurrence["id"])

    r = client.get(f"{API}/tasks/{task['id']}/comments/", headers=owner)
    assert r.status_code == 200, r.text
    [comment] = r.json()["data"]

    entries = _entries(db, owner_id)[len(seen) :]
    assert [entry.action for entry in entries] == [
        "task_completed",
        "task_created",
        "comment_added",
    ]
    completed, created, added = entries

    assert completed.entity_id == uuid.UUID(task["id"])
    assert completed.details == {"title": "Water the plants"}

    assert created.entity_id == uuid.UUID(successor_id)
    assert created.details["title"] == "Water the plants"
    snapshot = created.details["task"]
    assert snapshot["status"] == "todo"
    assert snapshot["due_date"] == next_due
    assert snapshot["project"] == {"id": project_id, "name": "Garden"}
    assert snapshot["assignee_id"] == closer["id"]
    assert snapshot["assignee"] == {
        "type": "bot_user",
        "id": closer["id"],
        "name": "Closer",
    }
    assert snapshot["recurrence"] == {"frequency": "weekly", "interval_days": None}
    assert snapshot["tags"] == []

    assert added.entity_id == uuid.UUID(comment["id"])
    assert added.details == {
        "task": {"id": task["id"], "title": "Water the plants"},
        "body": "Watered and fed.",
    }

    # Every entry this act wrote is the Closer bot's, never the owner's
    # (FR-10.2): the fact AC2 names, asserted for all three at once.
    assert all(entry.actor_bot_user_id == uuid.UUID(closer["id"]) for entry in entries)
    assert all(entry.actor_id is None for entry in entries)

    closer_outbox = outbox(db, closer["id"])
    watcher_outbox = outbox(db, watcher["id"])
    # AC3: a bot closing a task assigned to itself stages no ready row for
    # itself — the next occurrence came to be in To do assigned to the
    # Closer bot, which would ordinarily be a `task.ready` delivery for it,
    # dropped because the bot that would receive it is the bot that caused it.
    assert closer_outbox == []
    [delivery] = watcher_outbox
    assert delivery.webhook == WebhookKind.COMMENT.value
    assert delivery.event == WebhookEventType.COMMENT_ADDED.value
    assert delivery.task_id == uuid.UUID(task["id"])
    assert delivery.comment_id == uuid.UUID(comment["id"])

    # The `db` fixture is session-scoped (`tests/conftest.py`): it empties the
    # database once, at the end of the whole run, not after each test. Left
    # alone, the Watcher bot's still-pending delivery above would sit in the
    # outbox for every test that runs after this one — including
    # `tests/paperless/test_handover.py`'s own drain, which counts every
    # pending row in the database and is not this file's to leave stray rows
    # for. Deleting the owner cascades through its project, tasks, bot users,
    # activity entries and this delivery, the same cleanup the suite performs
    # for every account at the end, done here instead of left for then.
    owner_row = db.get(User, owner_id)
    assert owner_row is not None
    db.delete(owner_row)
    db.commit()


def test_two_commits_touching_one_entity_are_two_entries_not_one() -> None:
    """
    The second case #278 names (AC4): an act that touches one entity twice
    across two commits — deliberately constructed, since nothing in the
    product does this today. `complete_task`'s own second commit touches a
    *new* `Comment`, never the task its first commit just closed, so the
    ordinary HTTP and MCP surfaces give `_collect`/`_write` no repeat visit to
    one row to pin. This test manipulates one `Session` directly instead — the
    shape a future two-step edit would take before it owned a transaction of
    its own — to put the collapse risk the module docstring describes
    somewhere a unit-of-work merge would actually have to break it: today,
    renaming the task in one commit and reprioritising it in a second writes
    two `task_changed` entries, each with only the field that commit touched;
    merged into one transaction, `_write` would diff the task once and write
    a single entry carrying both — same net change, one fewer record of it
    having been two decisions. A deliberate change to this pinned sequence
    means editing this test in the same commit.

    Its own `Session` (`app.mcp.conventions.open_caller`'s own shape, one
    `with Session(engine)` per act) rather than the suite's shared `db`
    fixture: `set_bot_actor` stores the acting bot on `session.info`, where
    only `_discard`'s `after_transaction_end` listener ever looks again, and
    nothing clears it between transactions. The shared fixture lives for the
    whole run, so setting it there would attribute every later test's own
    direct `db` writes to a bot this test is about to delete — the next one
    to flush an entry through it would fail its own insert, a foreign key
    pointing at a bot user gone with this test's owner.
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

        # First commit: the title changes.
        task.title = "Draft the quarterly report"
        session.add(task)
        session.commit()

        # Second commit, the same task again: the priority changes. No
        # request path commits twice against one entity within one act; this
        # line is that shape, built by hand.
        task.priority = TaskPriority.P1
        session.add(task)
        session.commit()

        entries = _entries(session, owner.id)[len(seen) :]
        assert [entry.action for entry in entries] == ["task_changed", "task_changed"]
        renamed, reprioritized = entries

        assert renamed.entity_id == task.id
        assert renamed.details["changes"] == {
            "title": {"from": "Draft the report", "to": "Draft the quarterly report"}
        }
        assert reprioritized.entity_id == task.id
        assert reprioritized.details["changes"] == {
            "priority": {"from": None, "to": "P1"}
        }
        # Two entries, not the one entry a merged transaction's single diff
        # would have written for the same net change — the collapse this
        # file exists to catch, made to happen on purpose so there is
        # something to catch it.
        assert (
            renamed.details["changes"].keys() != reprioritized.details["changes"].keys()
        )
        assert all(entry.actor_bot_user_id == bot.id for entry in entries)
        assert all(entry.actor_id is None for entry in entries)

        # The suite's shared `db` fixture only empties itself once, at the
        # end of the whole run (`tests/conftest.py`); left behind, this
        # owner would sit in the database for every test that runs after
        # this one.
        session.delete(owner)
        session.commit()
