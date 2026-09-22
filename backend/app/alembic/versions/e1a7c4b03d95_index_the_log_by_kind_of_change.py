"""Index the activity log by kind of change

Revision ID: e1a7c4b03d95
Revises: c9e1f4a7b2d3
Create Date: 2026-09-22 00:00:00.000000

The log is kept indefinitely (FR-10.5), so narrowing it to one kind of change
must not mean walking every entry a user has ever accumulated to find the few
that match. Owner first, then action, then position: the same shape as the
index that carries one bot user's own feed.
"""

from alembic import op

revision = "e1a7c4b03d95"
down_revision = "c9e1f4a7b2d3"
branch_labels = None
depends_on = None

INDEX = "ix_activityentry_owner_id_action_position"


def upgrade() -> None:
    op.create_index(
        INDEX,
        "activityentry",
        ["owner_id", "action", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="activityentry")
