"""
The webhooks migration, run against a database of its own.

The suite's database is already at head and full of other tests' rows, so the
round trip happens in a scratch database next to it, created and dropped here.
"""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.db import engine

BEFORE = "b5e8a1d4c926"
AFTER = "d6a2f8b1c493"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_webhooks_migration"
    admin = create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))
        conn.execute(text(f'CREATE DATABASE "{database}"'))
    scratch = create_engine(engine.url.set(database=database))
    try:
        with scratch.connect() as conn:
            yield conn
    finally:
        scratch.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))
        admin.dispose()


def _migrate(connection: Connection, direction: str, revision: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "app/alembic"))
    config.attributes["connection"] = connection
    getattr(command, direction)(config, revision)
    connection.commit()


def _columns(connection: Connection, table: str) -> set[str]:
    rows = connection.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name=:t"),
        {"t": table},
    ).all()
    return {row.column_name for row in rows}


def _tables(connection: Connection) -> set[str]:
    rows = connection.execute(
        text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
    ).all()
    return {row.table_name for row in rows}


def _types(connection: Connection) -> set[str]:
    rows = connection.execute(
        text("SELECT typname FROM pg_type WHERE typtype = 'e'")
    ).all()
    return {row.typname for row in rows}


def _seed_bot(connection: Connection) -> uuid.UUID:
    user_id, bot_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text(
            'INSERT INTO "user" (id, email, is_active, is_superuser, session_version) '
            "VALUES (:id, 'webhooks@example.com', true, false, 0)"
        ),
        {"id": user_id},
    )
    connection.execute(
        text(
            "INSERT INTO botuser (id, name, owner_id, create_tasks, read_tasks, "
            "update_tasks, delete_tasks, add_comments, create_tags) "
            "VALUES (:id, 'Agent', :owner, true, true, true, true, true, true)"
        ),
        {"id": bot_id, "owner": user_id},
    )
    connection.commit()
    return bot_id


def test_round_trip_and_the_downgrade_leaves_no_type_behind(
    connection: Connection,
) -> None:
    _migrate(connection, "upgrade", BEFORE)
    types_before = _types(connection)
    bot_id = _seed_bot(connection)

    _migrate(connection, "upgrade", AFTER)

    assert {"task_webhook_url", "comment_webhook_url", "webhook_secret_encrypted"} <= (
        _columns(connection, "botuser")
    )
    assert "webhookdelivery" in _tables(connection)
    # An existing bot user starts with no webhooks and no secret.
    row = connection.execute(
        text(
            "SELECT task_webhook_url, comment_webhook_url, webhook_secret_encrypted "
            "FROM botuser WHERE id = :id"
        ),
        {"id": bot_id},
    ).one()
    assert tuple(row) == (None, None, None)
    # What the migration made is plain columns: no database enum to drop.
    assert _types(connection) == types_before

    _migrate(connection, "downgrade", BEFORE)
    assert "webhookdelivery" not in _tables(connection)
    assert not {
        "task_webhook_url",
        "comment_webhook_url",
        "webhook_secret_encrypted",
    } & _columns(connection, "botuser")
    assert _types(connection) == types_before

    # And it goes up again: nothing the downgrade left in the way.
    _migrate(connection, "upgrade", AFTER)
    assert "webhookdelivery" in _tables(connection)


def test_the_outbox_refuses_a_state_or_webhook_it_does_not_know(
    connection: Connection,
) -> None:
    _migrate(connection, "upgrade", AFTER)
    bot_id = _seed_bot(connection)

    def insert(webhook: str, state: str) -> None:
        connection.execute(
            text(
                "INSERT INTO webhookdelivery (id, bot_user_id, webhook, event, "
                "occurred_at, state, attempts, next_attempt_at) "
                "VALUES (:id, :bot, :webhook, 'test', now(), :state, 0, now())"
            ),
            {"id": uuid.uuid4(), "bot": bot_id, "webhook": webhook, "state": state},
        )

    insert("task", "pending")
    connection.commit()
    with pytest.raises(IntegrityError):
        insert("task", "sent")
    connection.rollback()
    with pytest.raises(IntegrityError):
        insert("status", "pending")
    connection.rollback()
