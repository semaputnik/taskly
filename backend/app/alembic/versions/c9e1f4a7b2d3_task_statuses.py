"""Replace completed with four task statuses

Revision ID: c9e1f4a7b2d3
Revises: b4e8d1c7a352
Create Date: 2026-09-17 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c9e1f4a7b2d3'
down_revision = 'b4e8d1c7a352'
branch_labels = None
depends_on = None

task_status = postgresql.ENUM(
    'todo', 'in_progress', 'waiting', 'done', name='taskstatus'
)

# At most one open occurrence per series, before and after.
OPEN_OCCURRENCE_BEFORE = 'NOT completed AND deletion_id IS NULL'
OPEN_OCCURRENCE_AFTER = "status <> 'done' AND deletion_id IS NULL"


def upgrade():
    task_status.create(op.get_bind())
    op.add_column(
        'task',
        sa.Column('status', task_status, nullable=False, server_default='todo'),
    )
    op.execute("UPDATE task SET status = 'done' WHERE completed")
    op.alter_column('task', 'status', server_default=None)

    op.drop_index('ix_task_one_open_occurrence', table_name='task')
    op.drop_column('task', 'completed')
    op.create_index(
        'ix_task_one_open_occurrence',
        'task',
        ['series_id'],
        unique=True,
        postgresql_where=sa.text(OPEN_OCCURRENCE_AFTER),
    )


def downgrade():
    op.add_column(
        'task',
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # In progress and waiting were open, so they go back to not completed.
    op.execute("UPDATE task SET completed = (status = 'done')")
    op.alter_column('task', 'completed', server_default=None)

    op.drop_index('ix_task_one_open_occurrence', table_name='task')
    op.drop_column('task', 'status')
    op.create_index(
        'ix_task_one_open_occurrence',
        'task',
        ['series_id'],
        unique=True,
        postgresql_where=sa.text(OPEN_OCCURRENCE_BEFORE),
    )
    # Dropping the column leaves its enum type behind, which would break the
    # next upgrade.
    task_status.drop(op.get_bind(), checkfirst=True)
