"""Add soft deletion

Revision ID: 45f76d0e533c
Revises: 596c5a18eb5c
Create Date: 2026-09-12 19:12:41.503118

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '45f76d0e533c'
down_revision = '596c5a18eb5c'
branch_labels = None
depends_on = None

# A deletion event names the one thing the user pointed at; the rest of what it
# took down is found through the deletion_id the rows carry.
TARGETS_ONE_THING = '(task_id IS NULL) <> (project_id IS NULL)'


def upgrade():
    op.create_table(
        'deletion',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='deletion_owner_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], name='deletion_task_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], name='deletion_project_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='deletion_pkey'),
        sa.CheckConstraint(TARGETS_ONE_THING, name='deletion_targets_one_thing'),
    )

    for table in ('task', 'project'):
        op.add_column(table, sa.Column('deletion_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f'{table}_deletion_id_fkey', table, 'deletion', ['deletion_id'], ['id'], ondelete='SET NULL'
        )
        op.create_index(op.f(f'ix_{table}_deletion_id'), table, ['deletion_id'])


def downgrade():
    # Deleted rows were never removed, so undoing soft deletion means removing
    # them for real — the state the database was in before this revision.
    op.execute('DELETE FROM task WHERE deletion_id IS NOT NULL')
    op.execute('DELETE FROM project WHERE deletion_id IS NOT NULL')

    for table in ('task', 'project'):
        op.drop_index(op.f(f'ix_{table}_deletion_id'), table_name=table)
        op.drop_constraint(f'{table}_deletion_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'deletion_id')

    op.drop_table('deletion')
