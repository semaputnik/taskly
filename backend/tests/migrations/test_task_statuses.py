"""
The task status migration, run against a database of its own.

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

BEFORE = "b4e8d1c7a352"
AFTER = "c9e1f4a7b2d3"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_migrations"
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


def _statuses(connection: Connection) -> dict[str, str]:
    rows = connection.execute(text("SELECT title, status FROM task")).all()
    return {row.title: row.status for row in rows}


def _completed(connection: Connection) -> dict[str, bool]:
    rows = connection.execute(text("SELECT title, completed FROM task")).all()
    return {row.title: row.completed for row in rows}


def _enum_exists(connection: Connection) -> bool:
    return bool(
        connection.scalar(
            text("SELECT count(*) FROM pg_type WHERE typname = 'taskstatus'")
        )
    )


def test_round_trip(connection: Connection) -> None:
    _migrate(connection, "upgrade", BEFORE)
    user_id, project_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text(
            'INSERT INTO "user" (id, email, is_active, is_superuser, hashed_password) '
            "VALUES (:id, 'migration@example.com', true, false, 'x')"
        ),
        {"id": user_id},
    )
    connection.execute(
        text(
            "INSERT INTO project (id, name, is_inbox, is_archived, owner_id) "
            "VALUES (:id, 'Inbox', true, false, :owner)"
        ),
        {"id": project_id, "owner": user_id},
    )
    for title, completed in (("finished", True), ("unfinished", False)):
        connection.execute(
            text(
                "INSERT INTO task (id, title, completed, owner_id, project_id) "
                "VALUES (:id, :title, :completed, :owner, :project)"
            ),
            {
                "id": uuid.uuid4(),
                "title": title,
                "completed": completed,
                "owner": user_id,
                "project": project_id,
            },
        )
    connection.commit()

    _migrate(connection, "upgrade", AFTER)
    assert _statuses(connection) == {"finished": "done", "unfinished": "todo"}

    connection.execute(
        text(
            "INSERT INTO task (id, title, status, owner_id, project_id) VALUES "
            "(:a, 'started', 'in_progress', :owner, :project), "
            "(:b, 'parked', 'waiting', :owner, :project)"
        ),
        {"a": uuid.uuid4(), "b": uuid.uuid4(), "owner": user_id, "project": project_id},
    )
    connection.commit()

    _migrate(connection, "downgrade", BEFORE)
    assert _completed(connection) == {
        "finished": True,
        "unfinished": False,
        "started": False,
        "parked": False,
    }
    assert not _enum_exists(connection)

    _migrate(connection, "upgrade", AFTER)
    assert _statuses(connection) == {
        "finished": "done",
        "unfinished": "todo",
        "started": "todo",
        "parked": "todo",
    }
    assert _enum_exists(connection)
