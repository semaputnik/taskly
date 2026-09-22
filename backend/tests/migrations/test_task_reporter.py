"""
The reporter migration, run against a database of its own.

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

BEFORE = "e1a7c4b03d95"
AFTER = "f4b2a9e17c30"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_reporter_migration"
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


def _reporters(connection: Connection) -> dict[str, tuple[uuid.UUID | None, ...]]:
    rows = connection.execute(
        text("SELECT title, reporter_id, reporter_bot_user_id FROM task")
    ).all()
    return {row.title: (row.reporter_id, row.reporter_bot_user_id) for row in rows}


def _columns(connection: Connection) -> set[str]:
    rows = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='task'"
        )
    ).all()
    return {row.column_name for row in rows}


def _seed(connection: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """An owner with a project, a bot user, and two tasks predating the change."""
    user_id, project_id, bot_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text(
            'INSERT INTO "user" (id, email, is_active, is_superuser, hashed_password) '
            "VALUES (:id, 'reporter@example.com', true, false, 'x')"
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
    connection.execute(
        text(
            "INSERT INTO botuser (id, name, owner_id, create_tasks, read_tasks, "
            "update_tasks, delete_tasks, add_comments, create_tags) "
            "VALUES (:id, 'Filing agent', :owner, true, true, true, true, true, true)"
        ),
        {"id": bot_id, "owner": user_id},
    )
    for title in ("filed by hand", "filed by a bot"):
        connection.execute(
            text(
                "INSERT INTO task (id, title, status, owner_id, project_id) "
                "VALUES (:id, :title, 'todo', :owner, :project)"
            ),
            {
                "id": uuid.uuid4(),
                "title": title,
                "owner": user_id,
                "project": project_id,
            },
        )
    connection.commit()
    return user_id, project_id, bot_id


def test_round_trip(connection: Connection) -> None:
    _migrate(connection, "upgrade", BEFORE)
    user_id, project_id, bot_id = _seed(connection)

    _migrate(connection, "upgrade", AFTER)

    # Every task that predates the change is attributed to its owner — the
    # decision taken with this migration, in place of reading the true author
    # out of the activity log.
    assert _reporters(connection) == {
        "filed by hand": (user_id, None),
        "filed by a bot": (user_id, None),
    }

    # A task filed afterwards can name a bot user instead.
    connection.execute(
        text(
            "INSERT INTO task (id, title, status, owner_id, project_id, "
            "reporter_bot_user_id) "
            "VALUES (:id, 'filed after', 'todo', :owner, :project, :bot)"
        ),
        {
            "id": uuid.uuid4(),
            "owner": user_id,
            "project": project_id,
            "bot": bot_id,
        },
    )
    connection.commit()
    assert _reporters(connection)["filed after"] == (None, bot_id)

    _migrate(connection, "downgrade", BEFORE)
    assert "reporter_id" not in _columns(connection)
    assert "reporter_bot_user_id" not in _columns(connection)

    _migrate(connection, "upgrade", AFTER)
    assert _reporters(connection) == {
        "filed by hand": (user_id, None),
        "filed by a bot": (user_id, None),
        # The downgrade dropped the column, so re-upgrading backfills this one
        # to the owner as well: the reporter is not recoverable once dropped.
        "filed after": (user_id, None),
    }


def test_a_task_cannot_have_two_reporters_or_none(connection: Connection) -> None:
    """
    The constraint is the whole point of the pair: a task has exactly one
    author, where it may have no assignee at all.
    """
    _migrate(connection, "upgrade", BEFORE)
    user_id, project_id, bot_id = _seed(connection)
    _migrate(connection, "upgrade", AFTER)

    def insert(title: str, reporter: uuid.UUID | None, bot: uuid.UUID | None) -> None:
        connection.execute(
            text(
                "INSERT INTO task (id, title, status, owner_id, project_id, "
                "reporter_id, reporter_bot_user_id) "
                "VALUES (:id, :title, 'todo', :owner, :project, :reporter, :bot)"
            ),
            {
                "id": uuid.uuid4(),
                "title": title,
                "owner": user_id,
                "project": project_id,
                "reporter": reporter,
                "bot": bot,
            },
        )

    with pytest.raises(IntegrityError):
        insert("nobody filed it", None, None)
    connection.rollback()

    with pytest.raises(IntegrityError):
        insert("two filed it", user_id, bot_id)
    connection.rollback()
