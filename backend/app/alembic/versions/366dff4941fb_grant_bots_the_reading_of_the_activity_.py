"""Grant bots the reading of the activity log

Revision ID: 366dff4941fb
Revises: a7c3e9d15b42
Create Date: 2026-10-12 02:02:58.727922

A new permission the owner grants explicitly, off by default (spec #246,
FR-08.9): reading the log does not follow from `read_tasks`, since the log
shows the owner's own work too. This migration only adds the column; what a
bot user with the grant may read is #251.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '366dff4941fb'
down_revision = 'a7c3e9d15b42'
branch_labels = None
depends_on = None


def upgrade():
    # Off for every bot user that exists already: a scope keeps granting
    # exactly what the user last saw, and reading the log was never part of
    # it.
    op.add_column(
        'botuser',
        sa.Column(
            'read_activity', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column('botuser', 'read_activity', server_default=None)


def downgrade():
    op.drop_column('botuser', 'read_activity')
