"""
The Paperless migration, run against a database of its own.

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

BEFORE = "d6a2f8b1c493"
AFTER = "a7c3e9d15b42"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_paperless_migration"
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


def _seed_attachment(connection: Connection) -> uuid.UUID:
    user_id, project_id, task_id, attachment_id = (uuid.uuid4() for _ in range(4))
    connection.execute(
        text(
            'INSERT INTO "user" (id, email, is_active, is_superuser, session_version) '
            "VALUES (:id, 'paperless@example.com', true, false, 0)"
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
            "INSERT INTO task (id, title, owner_id, project_id, status, reporter_id) "
            "VALUES (:id, 'T', :owner, :project, 'todo', :owner)"
        ),
        {"id": task_id, "owner": user_id, "project": project_id},
    )
    connection.execute(
        text(
            "INSERT INTO attachment (id, task_id, owner_id, filename, content_type, size) "
            "VALUES (:id, :task, :owner, 'a.pdf', 'application/pdf', 5)"
        ),
        {"id": attachment_id, "task": task_id, "owner": user_id},
    )
    connection.commit()
    return attachment_id


def test_round_trip_and_the_downgrade_leaves_no_type_behind(
    connection: Connection,
) -> None:
    _migrate(connection, "upgrade", BEFORE)
    types_before = _types(connection)
    attachment_id = _seed_attachment(connection)

    _migrate(connection, "upgrade", AFTER)

    assert "paperless_document_id" in _columns(connection, "attachment")
    assert {"paperlessconnection", "paperlesshandover"} <= _tables(connection)
    # An existing attachment is kept in Taskly: it points at no document.
    document_id = connection.execute(
        text("SELECT paperless_document_id FROM attachment WHERE id = :id"),
        {"id": attachment_id},
    ).scalar_one()
    assert document_id is None
    # Plain columns and check constraints: no database enum to drop.
    assert _types(connection) == types_before

    _migrate(connection, "downgrade", BEFORE)
    assert not {"paperlessconnection", "paperlesshandover"} & _tables(connection)
    assert "paperless_document_id" not in _columns(connection, "attachment")
    assert _types(connection) == types_before

    # And it goes up again: nothing the downgrade left in the way.
    _migrate(connection, "upgrade", AFTER)
    assert "paperlesshandover" in _tables(connection)


def test_the_handover_outbox_refuses_a_state_or_stage_it_does_not_know(
    connection: Connection,
) -> None:
    _migrate(connection, "upgrade", AFTER)
    attachment_id = _seed_attachment(connection)

    def insert(attachment: uuid.UUID, state: str, stage: str) -> None:
        connection.execute(
            text(
                "INSERT INTO paperlesshandover (id, attachment_id, state, stage, "
                "attempts, next_attempt_at) "
                "VALUES (:id, :attachment, :state, :stage, 0, now())"
            ),
            {
                "id": uuid.uuid4(),
                "attachment": attachment,
                "state": state,
                "stage": stage,
            },
        )

    insert(attachment_id, "pending", "send")
    connection.commit()
    with pytest.raises(IntegrityError):
        insert(attachment_id, "pending", "send")  # one per attachment
    connection.rollback()
    with pytest.raises(IntegrityError):
        insert(uuid.uuid4(), "delivered", "send")
    connection.rollback()
    with pytest.raises(IntegrityError):
        insert(uuid.uuid4(), "pending", "upload")
    connection.rollback()
