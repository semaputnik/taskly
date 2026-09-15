"""Add recurring tasks

Revision ID: 8b31a6e07580
Revises: 7b3e9a1c4d2f
Create Date: 2026-09-15 15:47:16.218634

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8b31a6e07580'
down_revision = '7b3e9a1c4d2f'
branch_labels = None
depends_on = None

recurrence_frequency = postgresql.ENUM(
    'daily', 'weekly', 'monthly', 'every_n_days', name='recurrencefrequency'
)

# Only "every N days" says what N is.
INTERVAL_DAYS_FOR_EVERY_N_DAYS = "(frequency = 'every_n_days') = (interval_days IS NOT NULL)"
# An occurrence always knows its place in the series it belongs to.
SERIES_STEP_WITH_SERIES = '(series_id IS NULL) = (series_step IS NULL)'
# At most one open occurrence per series.
OPEN_OCCURRENCE = 'NOT completed AND deletion_id IS NULL'


def upgrade():
    op.create_table(
        'series',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('frequency', recurrence_frequency, nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=True),
        sa.Column('anchor_date', sa.Date(), nullable=False),
        sa.Column('anchor_step', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='series_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='series_pkey'),
        sa.CheckConstraint(INTERVAL_DAYS_FOR_EVERY_N_DAYS, name='series_interval_days_for_every_n_days'),
    )

    op.add_column('task', sa.Column('series_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('task', sa.Column('series_step', sa.Integer(), nullable=True))
    op.create_foreign_key('task_series_id_fkey', 'task', 'series', ['series_id'], ['id'])
    op.create_index(op.f('ix_task_series_id'), 'task', ['series_id'])
    op.create_index(
        'ix_task_one_open_occurrence',
        'task',
        ['series_id'],
        unique=True,
        postgresql_where=sa.text(OPEN_OCCURRENCE),
    )
    op.create_check_constraint('task_series_step_with_series', 'task', SERIES_STEP_WITH_SERIES)


def downgrade():
    op.drop_constraint('task_series_step_with_series', 'task', type_='check')
    op.drop_index('ix_task_one_open_occurrence', table_name='task')
    op.drop_index(op.f('ix_task_series_id'), table_name='task')
    op.drop_constraint('task_series_id_fkey', 'task', type_='foreignkey')
    op.drop_column('task', 'series_step')
    op.drop_column('task', 'series_id')

    op.drop_table('series')
    # Dropping the table leaves its enum type behind, which would break the
    # next upgrade.
    recurrence_frequency.drop(op.get_bind(), checkfirst=True)
