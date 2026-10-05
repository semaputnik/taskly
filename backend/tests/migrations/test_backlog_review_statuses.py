"""
The migration that adds Backlog and Review (semaputnik/taskly#134, ADR-0008),
run against a scratch database of its own, as the four-status one is.
"""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text

from app.core.db import engine

BEFORE = "f4b2a9e17c30"
AFTER = "a7d3c5e9b104"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_status_migration"
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


def _enum_values(connection: Connection) -> list[str]:
    rows = connection.execute(
        text(
            "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid = enumtypid "
            "WHERE typname = 'taskstatus' ORDER BY enumsortorder"
        )
    ).all()
    return [row.enumlabel for row in rows]


def _insert(
    connection: Connection,
    *,
    owner: uuid.UUID,
    project: uuid.UUID,
    tasks: dict[str, str],
) -> None:
    for title, status in tasks.items():
        connection.execute(
            text(
                "INSERT INTO task (id, title, status, owner_id, project_id, "
                "reporter_id) VALUES (:id, :title, :status, :owner, :project, :owner)"
            ),
            {
                "id": uuid.uuid4(),
                "title": title,
                "status": status,
                "owner": owner,
                "project": project,
            },
        )
    connection.commit()


def test_round_trip(connection: Connection) -> None:
    _migrate(connection, "upgrade", BEFORE)
    owner, project = uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text(
            'INSERT INTO "user" (id, email, is_active, is_superuser, hashed_password) '
            "VALUES (:id, 'migration@example.com', true, false, 'x')"
        ),
        {"id": owner},
    )
    connection.execute(
        text(
            "INSERT INTO project (id, name, is_inbox, is_archived, owner_id) "
            "VALUES (:id, 'Inbox', true, false, :owner)"
        ),
        {"id": project, "owner": owner},
    )
    existing = {
        "planned": "todo",
        "started": "in_progress",
        "parked": "waiting",
        "finished": "done",
    }
    _insert(connection, owner=owner, project=project, tasks=existing)

    _migrate(connection, "upgrade", AFTER)
    # Existing rows are untouched: nothing was in Backlog or Review before.
    assert _statuses(connection) == existing
    assert _enum_values(connection) == [
        "backlog",
        "todo",
        "in_progress",
        "review",
        "waiting",
        "done",
    ]
    _insert(
        connection,
        owner=owner,
        project=project,
        tasks={"noted": "backlog", "handed over": "review"},
    )

    _migrate(connection, "downgrade", BEFORE)
    # Each new status falls back to its nearest open neighbour: Backlog was
    # To do before it had a name, and Review is work still on the main road.
    assert _statuses(connection) == {
        **existing,
        "noted": "todo",
        "handed over": "in_progress",
    }
    assert _enum_values(connection) == ["todo", "in_progress", "waiting", "done"]

    _migrate(connection, "upgrade", AFTER)
    assert "review" in _enum_values(connection)
    _insert(connection, owner=owner, project=project, tasks={"again": "review"})
    assert _statuses(connection)["again"] == "review"
