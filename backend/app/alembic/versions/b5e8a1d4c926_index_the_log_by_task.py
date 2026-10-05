"""Index the activity log by task

Revision ID: b5e8a1d4c926
Revises: a9d3f7c2e815
Create Date: 2026-10-05 00:00:00.000000

The log is kept indefinitely (FR-10.5), and a task's panel reads that one
task's history each time it opens. A task's own entries name it by entity id;
the entries of its comments and files name it inside their details. Both get
an index, owner first, so neither read walks everything a user has ever done.
"""

import sqlalchemy as sa
from alembic import op

revision = "b5e8a1d4c926"
down_revision = "a9d3f7c2e815"
branch_labels = None
depends_on = None

BY_ENTITY = "ix_activityentry_owner_id_entity_id"
BY_TASK = "ix_activityentry_owner_id_task"


def upgrade() -> None:
    op.create_index(BY_ENTITY, "activityentry", ["owner_id", "entity_id"])
    op.create_index(
        BY_TASK,
        "activityentry",
        ["owner_id", sa.text("(details -> 'task' ->> 'id')")],
    )


def downgrade() -> None:
    op.drop_index(BY_TASK, table_name="activityentry")
    op.drop_index(BY_ENTITY, table_name="activityentry")
