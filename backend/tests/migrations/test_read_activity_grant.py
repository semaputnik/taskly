"""
The `read_activity` migration, run against a database of its own (issue #250).

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

from app.core.db import engine

BEFORE = "a7c3e9d15b42"
AFTER = "366dff4941fb"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_read_activity_migration"
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


def _types(connection: Connection) -> set[str]:
    rows = connection.execute(
        text("SELECT typname FROM pg_type WHERE typtype = 'e'")
    ).all()
    return {row.typname for row in rows}


def _seed_bot(connection: Connection) -> uuid.UUID:
    """An owner with a bot user predating the grant."""
    user_id, bot_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text(
            'INSERT INTO "user" (id, email, is_active, is_superuser, session_version) '
            "VALUES (:id, 'read-activity@example.com', true, false, 0)"
        ),
        {"id": user_id},
    )
    connection.execute(
        text(
            "INSERT INTO botuser (id, name, owner_id, create_tasks, read_tasks, "
            "update_tasks, delete_tasks, add_comments, create_tags) "
            "VALUES (:id, 'Veteran agent', :owner, true, true, true, true, true, true)"
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

    assert "read_activity" in _columns(connection, "botuser")
    # An existing bot user is unaffected: the grant arrives off, and nothing
    # else about it changes (issue #250's acceptance).
    row = connection.execute(
        text("SELECT name, create_tasks, read_activity FROM botuser WHERE id = :id"),
        {"id": bot_id},
    ).one()
    assert tuple(row) == ("Veteran agent", True, False)
    # A plain column: no database enum for the downgrade to leave behind.
    assert _types(connection) == types_before

    connection.execute(
        text("UPDATE botuser SET read_activity = true WHERE id = :id"), {"id": bot_id}
    )
    connection.commit()
    assert connection.execute(
        text("SELECT read_activity FROM botuser WHERE id = :id"), {"id": bot_id}
    ).scalar_one()

    _migrate(connection, "downgrade", BEFORE)
    assert "read_activity" not in _columns(connection, "botuser")
    assert _types(connection) == types_before

    # And it goes up again: nothing the downgrade left in the way, and a
    # dropped grant comes back off, like any fresh column would.
    _migrate(connection, "upgrade", AFTER)
    assert "read_activity" in _columns(connection, "botuser")
    assert (
        connection.execute(
            text("SELECT read_activity FROM botuser WHERE id = :id"), {"id": bot_id}
        ).scalar_one()
        is False
    )
