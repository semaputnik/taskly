"""Assign tasks to bot users

Revision ID: e8b4d2f6a013
Revises: d7a1c3e5f902
Create Date: 2026-09-15 23:40:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e8b4d2f6a013'
down_revision = 'd7a1c3e5f902'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'botuser', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'task',
        sa.Column('assignee_bot_user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'task_assignee_bot_user_id_fkey',
        'task',
        'botuser',
        ['assignee_bot_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_check_constraint(
        'task_one_assignee',
        'task',
        'assignee_id IS NULL OR assignee_bot_user_id IS NULL',
    )


def downgrade():
    # A task assigned to a bot user has no user to hand it to without claiming
    # the owner took it on, so it goes back to nobody.
    op.drop_constraint('task_one_assignee', 'task', type_='check')
    op.drop_constraint('task_assignee_bot_user_id_fkey', 'task', type_='foreignkey')
    op.drop_column('task', 'assignee_bot_user_id')
    op.drop_column('botuser', 'deleted_at')
