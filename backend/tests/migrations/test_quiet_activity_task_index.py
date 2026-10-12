"""
Guards against #293: a spurious rewrite of the activity task index on every
`alembic revision --autogenerate` run.

`ActivityEntry` declares `ix_activityentry_owner_id_task` as a raw SQL
expression (`ACTIVITY_TASK_REF` in `app/models/activity.py`) so the index and
the activity-log filter that reads it are exactly one spelling. Postgres
normalizes that expression with explicit casts once the index exists, which
used to differ from the model's spelling — autogenerate read the stored index
as changed and proposed dropping and recreating it, on every run, on any
branch.

This runs against a scratch database of its own, as the other migration
tests do, and checks both that the index Postgres actually stores still
matches `ACTIVITY_TASK_REF` byte for byte, and that Alembic's own autogenerate
comparison — the thing `alembic revision --autogenerate` runs — finds nothing
to do at head.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import produce_migrations
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, text

from app.core.db import engine
from app.models import SQLModel
from app.models.activity import ACTIVITY_TASK_REF

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def connection() -> Generator[Connection]:
    database = f"{engine.url.database}_quiet_index_migration"
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


def _upgrade_head(connection: Connection) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "app/alembic"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    connection.commit()


def test_index_keeps_its_definition_after_upgrade_head(connection: Connection) -> None:
    _upgrade_head(connection)

    indexdef = connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'ix_activityentry_owner_id_task'"
        )
    ).scalar_one()

    assert indexdef == (
        "CREATE INDEX ix_activityentry_owner_id_task ON public.activityentry "
        f"USING btree (owner_id, ({ACTIVITY_TASK_REF}))"
    )


def test_autogenerate_is_empty_at_head(connection: Connection) -> None:
    _upgrade_head(connection)

    context = MigrationContext.configure(
        connection=connection, opts={"compare_type": True}
    )
    migrations = produce_migrations(context, SQLModel.metadata)

    upgrade_ops = migrations.upgrade_ops
    assert upgrade_ops is not None
    assert upgrade_ops.is_empty(), upgrade_ops.as_diffs()
