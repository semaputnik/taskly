"""
Guards the `app/models.py` -> `app/models/` package split (#280, parent #275).

Alembic's `env.py` imports `SQLModel` from `app.models` and binds
`target_metadata` to its `.metadata`, relying entirely on every table class
body having executed as a side effect of that one import (`app/core/db.py`
states the same contract). If the split's package `__init__.py` ever forgets
to import one domain module, that module's table classes never run,
`SQLModel.metadata` loses the table, and the next
`alembic revision --autogenerate` quietly writes an `op.drop_table` for a
table that is still very much there — a migration nobody meant to write.

This holds the metadata's tables up against the database's own: the suite's
database is migrated to Alembic's head before pytest runs
(`scripts/test.sh`), so every table a migration created is there regardless
of which classes happened to import this run. A table the database has but
the metadata doesn't means a domain module's import was dropped — exactly
the failure #280 must not introduce. A table the metadata has but the
database doesn't means a new table model landed without the migration that
creates it. Checking both directions, rather than only checking that the
expected tables are present, is what makes a *new*, unaccounted-for table
fail loudly instead of passing silently.

What this cannot catch: it is table-level only. A column added to or
dropped from an existing table's model, without a matching migration, leaves
the table's name registered either way and passes this test untouched.
"""

from sqlalchemy import inspect
from sqlmodel import SQLModel

import app.models  # noqa: F401 -- the import side effect this test pins down
from app.core.db import engine


def test_metadata_registers_every_table() -> None:
    inspector = inspect(engine)
    database_tables = set(inspector.get_table_names()) - {"alembic_version"}
    metadata_tables = set(SQLModel.metadata.tables.keys())

    missing_from_metadata = database_tables - metadata_tables
    extra_in_metadata = metadata_tables - database_tables

    assert not missing_from_metadata, (
        f"{sorted(missing_from_metadata)} exist in the database (migrated to "
        "head) but are not registered in SQLModel.metadata after importing "
        "app.models. Likely cause: a domain module defining one of these "
        "tables is not imported by app/models/__init__.py (or app/models.py), "
        "so its class body never ran. Alembic's autogenerate would read this "
        "as the table having been dropped and write `op.drop_table` for it."
    )
    assert not extra_in_metadata, (
        f"{sorted(extra_in_metadata)} are registered in SQLModel.metadata but "
        "do not exist in the database migrated to head. Likely cause: a new "
        "table model was added without the migration that creates it — run "
        "`alembic revision --autogenerate` to add one."
    )
