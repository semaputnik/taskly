"""Add the Backlog and Review statuses

Revision ID: a7d3c5e9b104
Revises: f4b2a9e17c30
Create Date: 2026-10-05 00:00:00.000000

Two open values join the status enum (ADR-0008): Backlog before To do and
Review after In progress, so the type's own order is the order the interface
lists them in. Existing rows keep the status they have.

Postgres can add a value to an enum but never remove one, so the downgrade
moves the rows off the new values, rebuilds the type with the four it had and
swaps the column over to it. The partial index on open occurrences compares
the column against a literal of the old type, so it goes first and comes back
last.
"""

import sqlalchemy as sa
from alembic import op

revision = "a7d3c5e9b104"
down_revision = "f4b2a9e17c30"
branch_labels = None
depends_on = None

OPEN_OCCURRENCE = "status <> 'done' AND deletion_id IS NULL"


def upgrade():
    # A value added inside a transaction cannot be used until it commits;
    # nothing in this migration uses either one.
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'backlog' BEFORE 'todo'")
    op.execute(
        "ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'review' AFTER 'in_progress'"
    )


def downgrade():
    # Backlog was To do before it had a name; Review is finished work still
    # open on the main road, which before it was In progress.
    op.execute("UPDATE task SET status = 'todo' WHERE status = 'backlog'")
    op.execute("UPDATE task SET status = 'in_progress' WHERE status = 'review'")

    op.drop_index("ix_task_one_open_occurrence", table_name="task")
    op.execute("ALTER TYPE taskstatus RENAME TO taskstatus_six")
    op.execute(
        "CREATE TYPE taskstatus AS ENUM ('todo', 'in_progress', 'waiting', 'done')"
    )
    op.execute(
        "ALTER TABLE task ALTER COLUMN status TYPE taskstatus "
        "USING status::text::taskstatus"
    )
    op.execute("DROP TYPE taskstatus_six")
    op.create_index(
        "ix_task_one_open_occurrence",
        "task",
        ["series_id"],
        unique=True,
        postgresql_where=sa.text(OPEN_OCCURRENCE),
    )
