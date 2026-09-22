"""Record who filed a task

Revision ID: f4b2a9e17c30
Revises: e1a7c4b03d95
Create Date: 2026-09-22 00:00:00.000000

Every task gains its reporter: the owner, or one of the owner's bot users,
in the same two-column shape the assignee already uses.

Existing tasks are attributed to their owner. The activity log holds the true
author of most of them — a `task_created` entry names the actor — so a
faithful backfill was possible and was deliberately not taken: the decision
was to attribute the whole of the existing history to the human. Tasks filed
by a bot user before this migration therefore name the owner, and only tasks
filed after it name a bot.

The columns go on nullable, are filled, and only then does the constraint
that exactly one of them is set go on — nothing else would hold against rows
that do not have a reporter yet.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4b2a9e17c30"
down_revision = "e1a7c4b03d95"
branch_labels = None
depends_on = None

CONSTRAINT = "task_one_reporter"


def upgrade() -> None:
    op.add_column(
        "task",
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "task",
        sa.Column("reporter_bot_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Neither key cascades: a bot user is soft-deleted and stays named on what
    # it filed, and losing an actor must never take the task down with it.
    op.create_foreign_key(
        "task_reporter_id_fkey", "task", "user", ["reporter_id"], ["id"]
    )
    op.create_foreign_key(
        "task_reporter_bot_user_id_fkey",
        "task",
        "botuser",
        ["reporter_bot_user_id"],
        ["id"],
    )

    op.execute("UPDATE task SET reporter_id = owner_id WHERE reporter_id IS NULL")

    op.create_check_constraint(
        CONSTRAINT,
        "task",
        "(reporter_id IS NULL) <> (reporter_bot_user_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "task", type_="check")
    op.drop_constraint("task_reporter_bot_user_id_fkey", "task", type_="foreignkey")
    op.drop_constraint("task_reporter_id_fkey", "task", type_="foreignkey")
    op.drop_column("task", "reporter_bot_user_id")
    op.drop_column("task", "reporter_id")
