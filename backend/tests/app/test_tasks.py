"""
`app.tasks.complete` (#275, #279): the operation itself, exercised directly
against its own `Session` rather than through either caller that normally
reaches it — the REST route or the MCP tool — both of which already resolve
a `Caller` through `app.api.deps`, which happens to call
`activity.set_bot_actor`/`set_actor` itself on the way. That coincidence is
exactly what #275 says FR-10.2 must not rest on: "a second caller already
exists, so attribution must not rest on every path happening to go through
the right dependency." This file calls the operation with a `Caller` built
by hand, never passed through `get_caller`/`get_mcp_caller`, so a passing
assertion here means the operation set the actor itself.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, col, select

from app import crud
from app.api.deps import Caller
from app.core.db import engine
from app.models import (
    ActivityEntry,
    BotPermissions,
    BotScope,
    BotUserCreate,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    User,
    UserCreate,
)
from app.tasks import complete
from tests.utils.utils import random_email


def _entries(session: Session, owner_id: uuid.UUID) -> list[ActivityEntry]:
    session.expire_all()
    return list(
        session.exec(
            select(ActivityEntry)
            .where(ActivityEntry.owner_id == owner_id)
            .order_by(col(ActivityEntry.position))
        ).all()
    )


def test_completing_a_task_through_the_operation_attributes_to_the_bot_not_the_owner() -> (
    None
):
    """
    AC2 of #279, asserted against the operation directly: `app.tasks.complete`
    is what sets the actor (`_set_actor`), not a dependency this test never
    calls. A `Caller` built here by hand, never resolved through
    `app.api.deps.get_caller`/`get_mcp_caller`, still attributes the close to
    the bot, never to its owner.
    """
    with Session(engine) as session:
        owner = crud.create_user(
            session=session, user_create=UserCreate(email=random_email())
        )
        inbox = crud.get_inbox_project(session=session, owner_id=owner.id)
        bot = crud.create_bot_user(
            session=session,
            bot_user_create=BotUserCreate(
                name="Closer",
                scope=BotScope(
                    project_ids=[inbox.id],
                    permissions=BotPermissions(update_tasks=True),
                ),
            ),
            owner_id=owner.id,
        )
        task = crud.create_task(
            session=session,
            task_create=TaskCreate(title="Ship it"),
            project_id=inbox.id,
            owner_id=owner.id,
            reporter=crud.Reporter(bot_user_id=bot.id),
        )
        seen = _entries(session, owner.id)

        # A `Caller` assembled by hand: nothing here calls `get_caller` or
        # `get_mcp_caller`, so if the entry below is attributed to the bot,
        # `complete` set the actor itself.
        caller = Caller(
            owner_id=owner.id, bot=bot, project_ids=frozenset([inbox.id])
        )
        result = complete(
            session, caller, task.id, TaskUpdate(status=TaskStatus.DONE)
        )

        assert result.task.status is TaskStatus.DONE
        entries = _entries(session, owner.id)[len(seen) :]
        [completed] = [e for e in entries if e.action == "task_completed"]
        assert completed.entity_id == task.id
        assert completed.actor_bot_user_id == bot.id
        assert completed.actor_id is None

        # The shared `db` fixture is session-scoped and outlives this test
        # (tests/conftest.py); this test opened its own session instead
        # (CLAUDE.md's own note on #288), so it cleans up after itself here.
        owner_row = session.get(User, owner.id)
        assert owner_row is not None
        session.delete(owner_row)
        session.commit()


def test_complete_decides_access_itself() -> None:
    """
    The operation decides access rather than taking it as already settled: a
    `Caller` whose scope does not reach the task's project is refused by
    `app.api.access.get_task` from inside `complete`, exactly as a route
    would be refused calling it directly.
    """
    with Session(engine) as session:
        owner = crud.create_user(
            session=session, user_create=UserCreate(email=random_email())
        )
        inbox = crud.get_inbox_project(session=session, owner_id=owner.id)
        bot = crud.create_bot_user(
            session=session,
            bot_user_create=BotUserCreate(
                name="Outsider",
                scope=BotScope(
                    project_ids=[], permissions=BotPermissions(update_tasks=True)
                ),
            ),
            owner_id=owner.id,
        )
        task = crud.create_task(
            session=session,
            task_create=TaskCreate(title="Ship it"),
            project_id=inbox.id,
            owner_id=owner.id,
            reporter=crud.Reporter(bot_user_id=bot.id),
        )
        caller = Caller(owner_id=owner.id, bot=bot, project_ids=frozenset())

        with pytest.raises(HTTPException) as exc_info:
            complete(session, caller, task.id, TaskUpdate(status=TaskStatus.DONE))
        assert exc_info.value.status_code == 403

        owner_row = session.get(User, owner.id)
        assert owner_row is not None
        session.delete(owner_row)
        session.commit()
